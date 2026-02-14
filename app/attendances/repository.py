"""Attendance repository for database operations."""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.attendances.models import Attendance, AttendanceChannel, AttendanceStatus
from app.attendances.objective_service import AttendanceObjectiveService
from app.attendances.schemas import AttendanceCreate, AttendanceUpdate
from app.ai.models import AISummary, AISummaryStatus
from app.ai.repository import AISummaryRepository
from app.ai.schemas import AISummaryCreate
from app.ai.service import AISummaryService
from app.clients.models import Client
from app.clients.repository import ClientRepository
from app.clients.score_service import LeadScoreService
from app.clients.schemas import ClientUpdate
from app.clients.state_derivation_service import ClientStateDerivationService
from app.visits.models import Visit, VisitStatus
from app.visits.repository import VisitRepository
from app.clients.timeline_models import ClientTimeline, TimelineEventType

logger = logging.getLogger(__name__)


class AttendanceRepository:
    """Repository for attendance database operations."""

    def __init__(self, db: Session) -> None:
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db


    def get_active_attendance_by_client(self, client_id: uuid.UUID) -> Attendance | None:
        """
        Get the active attendance for a client.
        
        This method ensures uniqueness: if multiple ACTIVE attendances exist,
        it closes all but the most recent one (data integrity fix).
        
        Args:
            client_id: Client UUID
            
        Returns:
            Active attendance instance or None if not found
        """
        stmt = (
            select(Attendance)
            .where(Attendance.client_id == client_id)
            .where(Attendance.status == AttendanceStatus.ACTIVE)
            .order_by(Attendance.created_at.desc())
        )
        active_attendances = list(self.db.scalars(stmt).all())
        
        if not active_attendances:
            return None
        
        if len(active_attendances) > 1:
            # Data integrity issue: multiple ACTIVE attendances exist
            # Close all but the most recent one
            logger.warning(
                f"Found {len(active_attendances)} ACTIVE attendances for client {client_id}. "
                "Closing all but the most recent one to maintain data integrity."
            )
            
            # Keep the most recent (first in list due to order_by desc)
            most_recent = active_attendances[0]
            
            # Close all others as ABANDONED (objective changed, cycle abandoned)
            for attendance in active_attendances[1:]:
                attendance.status = AttendanceStatus.ABANDONED
                
                self._add_timeline_event(
                    client_id=client_id,
                    event_type=TimelineEventType.ATTENDANCE_COMPLETED,
                    title="Ciclo abandonado (múltiplos ACTIVE detectados)",
                    description="Ciclo fechado automaticamente para manter integridade dos dados",
                    related_attendance_id=attendance.id,
                    event_data={
                        "reason": "multiple_active_fix",
                    },
                )
            
            self.db.flush()
            return most_recent
        
        return active_attendances[0]
    
    def _close_active_attendance(
        self,
        attendance: Attendance,
        new_status: AttendanceStatus = AttendanceStatus.ABANDONED,
        reason: str = "Novo ciclo iniciado",
    ) -> None:
        """
        Close an active attendance explicitly.
        
        Args:
            attendance: Attendance to close
            new_status: Status to set (ABANDONED, COMPLETED, or LOST)
            reason: Reason for closing (for timeline event)
        """
        if attendance.status != AttendanceStatus.ACTIVE:
            return  # Already closed
        
        attendance.status = new_status
        
        self._add_timeline_event(
            client_id=attendance.client_id,
            event_type=TimelineEventType.ATTENDANCE_COMPLETED,
            title=f"Ciclo fechado: {new_status.value}",
            description=reason,
            related_attendance_id=attendance.id,
            event_data={
                "previous_status": "ACTIVE",
                "new_status": new_status.value,
            },
        )
        
        self.db.flush()
        logger.info(
            f"Closed attendance {attendance.id} for client {attendance.client_id} "
            f"with status {new_status.value}. Reason: {reason}"
        )

    def create(self, attendance_data: AttendanceCreate) -> Attendance:
        """
        Create a new attendance or update existing active attendance based on objective.
        
        This method implements the goal-oriented cycle logic:
        - Detects objective from raw_content
        - Checks if there's an active attendance with similar objective
        - Creates new attendance if objective changed significantly
        - Updates existing attendance if same objective (accumulates conversations)
        
        **Concurrency Safety:**
        - Uses database-level locking to prevent race conditions
        - Ensures only one ACTIVE attendance per client even with concurrent requests
        
        Args:
            attendance_data: Attendance creation data

        Returns:
            Created or updated attendance instance
        """
        # Use database transaction with row-level lock to prevent race conditions
        # This ensures only one ACTIVE attendance per client even with concurrent requests
        from sqlalchemy import select
        
        # Lock the client row to prevent concurrent attendance creation
        # This prevents the race condition where two requests simultaneously:
        # 1. Check for existing ACTIVE attendance (both find None)
        # 2. Create new ACTIVE attendance (both create, violating uniqueness)
        client = self.db.execute(
            select(Client)
            .where(Client.id == attendance_data.client_id)
            .with_for_update(nowait=False)  # Wait for lock, prevents race condition
        ).scalar_one_or_none()
        
        if not client:
            raise ValueError(f"Client {attendance_data.client_id} not found")
        
        client_data = {
            "current_interest_type": client.current_interest_type.value if client.current_interest_type else None,
            "current_city_interest": client.current_city_interest,
            "current_property_type": client.current_property_type.value if client.current_property_type else None,
        }
        
        # Detect objective from raw_content
        structured_objective, human_readable_objective = AttendanceObjectiveService.detect_objective(
            raw_content=attendance_data.raw_content,
            client_data=client_data,
        )
        
        # Get existing active attendance for this client (with lock to prevent race condition)
        # This query is now safe because we have the client row locked
        existing_active_attendance = self.get_active_attendance_by_client(attendance_data.client_id)
        
        # Determine if should create new or update existing
        should_create_new = AttendanceObjectiveService.should_create_new_attendance(
            client_id=attendance_data.client_id,
            new_objective=structured_objective,
            existing_active_attendance=existing_active_attendance,
            db=self.db,
            raw_content=attendance_data.raw_content,
        )
        
        if should_create_new or not existing_active_attendance:
            # Close existing active attendance if creating new one
            if existing_active_attendance:
                # Determine closure reason based on objective change
                if structured_objective and existing_active_attendance.objective:
                    reason = f"Objetivo mudou: '{existing_active_attendance.objective}' → '{human_readable_objective}'"
                else:
                    reason = "Novo ciclo iniciado"
                
                self._close_active_attendance(
                    attendance=existing_active_attendance,
                    new_status=AttendanceStatus.ABANDONED,  # Objective changed, previous cycle abandoned
                    reason=reason,
                )
            
            # Create new attendance
            return self._create_new_attendance(
                attendance_data=attendance_data,
                objective=human_readable_objective,
            )
        else:
            # Update existing attendance (accumulate conversations)
            return self._update_existing_attendance(
                existing_attendance=existing_active_attendance,
                new_content=attendance_data.raw_content,
                attendance_data=attendance_data,
            )
    
    def _create_new_attendance(
        self,
        attendance_data: AttendanceCreate,
        objective: str | None,
    ) -> Attendance:
        """
        Create a new attendance with detected objective.
        
        Args:
            attendance_data: Attendance creation data
            objective: Detected objective (human-readable string)
            
        Returns:
            Created attendance instance
        """
        attendance_dict = attendance_data.model_dump(exclude_unset=False)

        # Set default status if not provided
        if "status" not in attendance_dict or attendance_dict["status"] is None:
            attendance_dict["status"] = AttendanceStatus.ACTIVE

        # Set objective if detected
        if objective:
            attendance_dict["objective"] = objective

        # Serialize updated_client_status to JSON string if provided
        if "updated_client_status" in attendance_dict and attendance_dict["updated_client_status"] is not None:
            client_status_update = attendance_dict.pop("updated_client_status")
            attendance_dict["updated_client_status"] = json.dumps(
                client_status_update.model_dump(exclude_unset=True) if hasattr(client_status_update, "model_dump") else client_status_update
            )

        db_attendance = Attendance(**attendance_dict)
        self.db.add(db_attendance)
        self.db.flush()  # Flush to get the attendance ID

        # Store values before commit (needed for timeline event after commit)
        attendance_id = db_attendance.id
        client_id = db_attendance.client_id
        channel_value = db_attendance.channel.value if db_attendance.channel else None
        status_value = db_attendance.status.value if db_attendance.status else None

        # Commit attendance FIRST to ensure it exists in database
        # This must happen before _generate_ai_summary because it may create timeline events
        self.db.commit()
        
        # Re-query attendance after commit (object is detached)
        db_attendance = self.db.get(Attendance, attendance_id)

        # Try to detect property mention from raw_content
        # This happens BEFORE AI summary generation so property_id is set correctly
        try:
            from app.ai.service import AISummaryService
            
            property_info = AISummaryService.detect_property_mention(
                raw_content=db_attendance.raw_content,
                db=self.db,
                current_property_id=db_attendance.property_id,
            )
            
            if property_info and property_info.get("detected"):
                detected_property_id = property_info.get("property_id")
                if detected_property_id:
                    logger.info(
                        f"Detected property {detected_property_id} for new attendance {attendance_id}. "
                        f"Setting property_id automatically."
                    )
                    db_attendance.property_id = detected_property_id
                    self.db.flush()
                    
                    # Add timeline event for property detection
                    self._add_timeline_event(
                        client_id=client_id,
                        event_type=TimelineEventType.PROPERTY_SELECTED,
                        title="Imóvel detectado automaticamente",
                        description=f"IA detectou menção ao imóvel {property_info.get('property_code', '')} na conversa inicial",
                        related_attendance_id=attendance_id,
                        related_property_id=detected_property_id,
                        event_data={
                            "property_code": property_info.get("property_code"),
                            "detection_method": property_info.get("detection_method"),
                            "confidence": property_info.get("confidence"),
                            "extracted_text": property_info.get("extracted_text"),
                        },
                        ai_generated=True,
                        importance=4,
                        auto_add=True,
                    )
        except Exception as e:
            logger.warning(f"Error detecting property mention in new attendance: {e}", exc_info=True)

        # Generate AI summary automatically (after commit to avoid foreign key issues)
        # Property_id is now set if detected, so AI summary will have correct context
        self._generate_ai_summary(db_attendance)

        # Update client status if provided
        if attendance_data.updated_client_status:
            self._update_client_from_attendance(db_attendance, attendance_data.updated_client_status)

        # Create visit if scheduled_visit_at is provided
        if attendance_data.scheduled_visit_at:
            self._create_visit_from_attendance(db_attendance)

        # Create timeline event (after commit to avoid foreign key constraint violation)
        self._add_timeline_event(
            client_id=client_id,
            event_type=TimelineEventType.ATTENDANCE_STARTED,
            title="Novo ciclo de atendimento iniciado",
            description=f"Objetivo: {objective or 'Não definido'} - Atendimento via {channel_value or 'canal desconhecido'}",
            related_attendance_id=attendance_id,
            event_data={
                "channel": channel_value,
                "status": status_value,
                "objective": objective,
            },
            auto_add=True,  # Safe to add now - attendance is already committed
        )
        
        # Commit timeline event
        self.db.commit()
        
        # Re-query attendance from database (object is detached after commit)
        db_attendance = self.db.get(Attendance, attendance_id)
        
        logger.info(
            f"Created new attendance {attendance_id} for client {client_id} "
            f"with objective: {objective}"
        )
        return db_attendance
    
    def _update_existing_attendance(
        self,
        existing_attendance: Attendance,
        new_content: str,
        attendance_data: AttendanceCreate,
    ) -> Attendance:
        """
        Update existing active attendance by accumulating new conversation content.
        
        **Protection:** Only updates attendances with status ACTIVE.
        Closed attendances (COMPLETED, LOST, ABANDONED) cannot receive new conversations.
        
        Args:
            existing_attendance: Existing active attendance to update
            new_content: New conversation content to add
            attendance_data: Attendance creation data (for other fields if needed)
            
        Returns:
            Updated attendance instance
            
        Raises:
            ValueError: If attendance is not ACTIVE (cycle is closed)
        """
        # PROTECTION: Only allow updates to ACTIVE attendances
        # Closed cycles (COMPLETED, LOST, ABANDONED) cannot receive new conversations
        if existing_attendance.status != AttendanceStatus.ACTIVE:
            logger.warning(
                f"Attempted to update closed attendance {existing_attendance.id} "
                f"(status: {existing_attendance.status.value}) for client {existing_attendance.client_id}. "
                "Closed cycles cannot receive new conversations. A new cycle should be created instead."
            )
            raise ValueError(
                f"Cannot update attendance {existing_attendance.id}: cycle is closed "
                f"(status: {existing_attendance.status.value}). "
                "Closed cycles cannot receive new conversations. Create a new attendance cycle instead."
            )
        
        # Accumulate raw_content (add new conversation to existing)
        # TODO: Consider content size limits (e.g., max 50k chars) to avoid:
        # - High AI processing costs
        # - Context loss in AI models
        # - Performance issues
        # Future optimization: Store conversations separately or truncate old content
        separator = "\n\n---\n\n"
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # Check if new_content already contains existing content (prevent duplication)
        # This can happen if frontend sends full content instead of just new part
        if new_content.startswith(existing_attendance.raw_content):
            # Frontend sent full content, extract only the new part
            new_part = new_content[len(existing_attendance.raw_content):].lstrip()
            # Remove separator if present
            if new_part.startswith(separator.strip()):
                new_part = new_part[len(separator.strip()):].lstrip()
            # Remove timestamp if present
            timestamp_pattern = r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\s*'
            new_part = re.sub(timestamp_pattern, '', new_part)
            accumulated_content = f"{existing_attendance.raw_content}{separator}[{timestamp}] {new_part}"
        else:
            # Normal case: new_content is just the new conversation
            accumulated_content = f"{existing_attendance.raw_content}{separator}[{timestamp}] {new_content}"
        
        # Warn if content is getting large (potential issue)
        if len(accumulated_content) > 10000:  # 10k chars threshold
            logger.warning(
                f"Attendance {existing_attendance.id} raw_content is large ({len(accumulated_content)} chars). "
                "Consider content management strategy."
            )
        
        # Update attendance with accumulated content
        existing_attendance.raw_content = accumulated_content
        
        # Update other fields if provided (channel, property_id, etc.)
        # IMPORTANT: Only update property_id if explicitly provided OR if detected by AI
        # If property_id is already set and client confirms it, keep it
        # Only change if a different property is detected
        if attendance_data.property_id:
            existing_attendance.property_id = attendance_data.property_id
        else:
            # Try to detect property mention from new content
            try:
                from app.ai.service import AISummaryService
                
                property_info = AISummaryService.detect_property_mention(
                    raw_content=accumulated_content,
                    db=self.db,
                    current_property_id=existing_attendance.property_id,
                )
                
                if property_info and property_info.get("detected"):
                    detected_property_id = property_info.get("property_id")
                    is_confirmation = property_info.get("is_confirmation", False)
                    
                    # If client confirmed current property, keep it (already set)
                    if is_confirmation and existing_attendance.property_id:
                        logger.info(
                            f"Client confirmed property {existing_attendance.property_id} "
                            f"for attendance {existing_attendance.id}"
                        )
                        # Add timeline event for confirmation
                        self._add_timeline_event(
                            client_id=existing_attendance.client_id,
                            event_type=TimelineEventType.PROPERTY_CONFIRMED,
                            title="Cliente confirmou imóvel",
                            description=f"Cliente confirmou/decidiu pelo imóvel {property_info.get('property_code', '')}",
                            related_attendance_id=existing_attendance.id,
                            related_property_id=existing_attendance.property_id,
                            event_data={
                                "property_code": property_info.get("property_code"),
                                "detection_method": property_info.get("detection_method"),
                                "confidence": property_info.get("confidence"),
                            },
                            ai_generated=True,
                            importance=5,
                            auto_add=True,
                        )
                    elif detected_property_id:
                        # Different property detected or new property
                        if not existing_attendance.property_id or str(detected_property_id) != str(existing_attendance.property_id):
                            logger.info(
                                f"Detected property {detected_property_id} for attendance {existing_attendance.id}. "
                                f"Previous: {existing_attendance.property_id}"
                            )
                            existing_attendance.property_id = detected_property_id
                            
                            # Add timeline event for property detection
                            self._add_timeline_event(
                                client_id=existing_attendance.client_id,
                                event_type=TimelineEventType.PROPERTY_SELECTED,
                                title="Imóvel detectado automaticamente",
                                description=f"IA detectou menção ao imóvel {property_info.get('property_code', '')} na conversa",
                                related_attendance_id=existing_attendance.id,
                                related_property_id=detected_property_id,
                                event_data={
                                    "property_code": property_info.get("property_code"),
                                    "detection_method": property_info.get("detection_method"),
                                    "confidence": property_info.get("confidence"),
                                    "extracted_text": property_info.get("extracted_text"),
                                },
                                ai_generated=True,
                                importance=4,
                                auto_add=True,
                            )
            except Exception as e:
                logger.warning(f"Error detecting property mention: {e}", exc_info=True)
        
        # Update scheduled_visit_at if provided and not already set
        if attendance_data.scheduled_visit_at and not existing_attendance.scheduled_visit_at:
            existing_attendance.scheduled_visit_at = attendance_data.scheduled_visit_at
            self._create_visit_from_attendance(existing_attendance)
        
        # Update client status if provided
        if attendance_data.updated_client_status:
            self._update_client_from_attendance(existing_attendance, attendance_data.updated_client_status)
        
        self.db.flush()
        
        # Regenerate AI summary with accumulated content
        # TODO: Optimize AI summary regeneration:
        # - Only regenerate if content changed significantly (e.g., >20% new content)
        # - Or mark as PENDING and process async to avoid blocking
        # - Or use incremental updates instead of full regeneration
        # Regenerate AI summary with accumulated content
        # _generate_ai_summary will update existing summary or create new one
        self._generate_ai_summary(existing_attendance)
        
        # Add timeline event for conversation update
        self._add_timeline_event(
            client_id=existing_attendance.client_id,
            event_type=TimelineEventType.ATTENDANCE_STARTED,
            title="Conversa adicionada ao ciclo atual",
            description=f"Nova interação via {attendance_data.channel.value if attendance_data.channel else 'canal desconhecido'}",
            related_attendance_id=existing_attendance.id,
            event_data={
                "channel": attendance_data.channel.value if attendance_data.channel else None,
                "content_length": len(new_content),
            },
        )
        
        self.db.commit()
        self.db.refresh(existing_attendance)
        logger.info(
            f"Updated existing attendance {existing_attendance.id} for client {existing_attendance.client_id} "
            f"with new conversation content"
        )
        return existing_attendance

    def _update_client_from_attendance(
        self,
        attendance: Attendance,
        client_status_update,
    ) -> None:
        """
        Update client status fields from attendance.
        
        NOTE: This method handles manual status updates only.
        AI-controlled fields (interest, budget, urgency, lead_score) are updated
        automatically through _update_client_from_ai_summary, which is called
        whenever an AI summary is generated or updated.
        
        The system is ALWAYS attentive to changes:
        - New attendance → AI analyzes → Updates client profile automatically
        - Attendance update → AI re-analyzes → Updates client profile automatically
        - All changes in interest, budget, urgency are detected and applied

        Args:
            attendance: Attendance instance
            client_status_update: ClientStatusUpdate schema
        """
        from app.clients.schemas import ClientUpdate

        client_repo = ClientRepository(self.db)
        client = client_repo.get_by_id(attendance.client_id)

        if not client:
            return

        # Prepare update data
        # NOTE: Only update current_status manually - other fields are AI-controlled
        # AI-controlled fields (current_interest_type, current_property_type, current_city_interest,
        # current_budget_min, current_budget_max) should be updated automatically by AI through
        # _update_client_from_ai_summary, not manually through this method
        update_data = {}
        if client_status_update.current_status:
            update_data["current_status"] = client_status_update.current_status
        
        # BLOCK manual updates to AI-controlled fields
        # These fields are updated automatically by AI through state derivation
        # If provided in client_status_update, they will be ignored
        if client_status_update.current_interest_type:
            logger.warning(
                f"Ignoring manual update to current_interest_type for client {attendance.client_id}. "
                "This field is controlled exclusively by AI."
            )
        if client_status_update.current_property_type:
            logger.warning(
                f"Ignoring manual update to current_property_type for client {attendance.client_id}. "
                "This field is controlled exclusively by AI."
            )

        if update_data:
            client_update = ClientUpdate(**update_data)
            # Do NOT allow AI updates here - this is for manual status updates only
            client_repo.update(client, client_update, allow_ai_updates=False)

    def _process_completed_attendance(self, attendance: Attendance) -> None:
        """
        Process completed attendance with full AI analysis.

        This method is called when an attendance is marked as COMPLETED.
        It performs comprehensive AI processing including:
        - Generating summary and next steps
        - Detecting intent, sentiment, urgency
        - Recommending properties
        - Updating client state

        Args:
            attendance: Attendance instance that was just completed
        """
        try:
            # Check if AI summary already exists
            from app.ai.repository import AISummaryRepository
            ai_repo = AISummaryRepository(self.db)
            existing_summary = ai_repo.get_by_attendance_id(attendance.id)

            if existing_summary:
                # If exists, mark as REPROCESSING and update
                existing_summary.status = AISummaryStatus.REPROCESSING
                self.db.flush()

            # Generate comprehensive AI summary with recommendations
            ai_data = AISummaryService.generate_summary(attendance, db=self.db)

            # Create or update AI summary record
            summary_data = AISummaryCreate(
                attendance_id=attendance.id,
                client_id=attendance.client_id,
                **ai_data,
            )

            if existing_summary:
                # Update existing summary
                from app.ai.schemas import AISummaryUpdate
                update_data = AISummaryUpdate(**summary_data.model_dump(exclude={"attendance_id", "client_id"}))
                ai_repo.update(existing_summary, update_data)
                ai_summary = existing_summary
            else:
                # Create new summary
                ai_summary = ai_repo.create(summary_data)

            # Update attendance's ai_summary and ai_next_steps fields
            if ai_summary.status.value == "COMPLETED":
                attendance.ai_summary = ai_summary.summary_text
                
                # Generate next steps from AI analysis
                next_steps = []
                if ai_summary.detected_intent:
                    intent_labels = {
                        "PROPERTY_SEARCH": "Buscar propriedades similares",
                        "SCHEDULE_VISIT": "Agendar visita",
                        "PRICE_NEGOTIATION": "Negociar preço",
                        "INFORMATION_REQUEST": "Enviar informações solicitadas",
                    }
                    intent_label = intent_labels.get(ai_summary.detected_intent.value, "Acompanhar cliente")
                    next_steps.append(intent_label)

                if ai_summary.interest_type_detected:
                    interest_type_labels = {
                        "BUY": "Comprar imóvel",
                        "RENT": "Alugar imóvel",
                        "SELL": "Vender imóvel",
                        "INVEST": "Investir em imóvel",
                    }
                    interest_type_value = ai_summary.interest_type_detected.value if hasattr(ai_summary.interest_type_detected, 'value') else str(ai_summary.interest_type_detected)
                    interest_label = interest_type_labels.get(interest_type_value, interest_type_value)
                    next_steps.append(f"Cliente interessado em: {interest_label}")
                
                if ai_summary.urgency_level_detected:
                    urgency_labels = {
                        "IMMEDIATE": "URGENTE - Contatar imediatamente",
                        "HIGH": "Alta prioridade - Contatar em até 24h",
                        "MEDIUM": "Média prioridade - Contatar em até 3 dias",
                        "LOW": "Baixa prioridade - Contatar em até 7 dias",
                    }
                    urgency_value = ai_summary.urgency_level_detected.value if hasattr(ai_summary.urgency_level_detected, 'value') else str(ai_summary.urgency_level_detected)
                    urgency_label = urgency_labels.get(urgency_value, urgency_value)
                    next_steps.append(urgency_label)

                if ai_summary.recommended_properties:
                    next_steps.append(f"Recomendar {len(ai_summary.recommended_properties)} propriedade(s) encontrada(s)")

                if next_steps:
                    attendance.ai_next_steps = "\n".join(f"• {step}" for step in next_steps)

                # Update client with AI-detected information
                self._update_client_from_ai_summary(attendance.client_id, ai_summary)
                
                # Add timeline event for completed attendance
                self._add_timeline_event(
                    client_id=attendance.client_id,
                    event_type=TimelineEventType.ATTENDANCE_COMPLETED,
                    title="Atendimento concluído",
                    description=ai_summary.summary_text[:200] if ai_summary.summary_text else "Atendimento finalizado",
                    related_attendance_id=attendance.id,
                    event_data={
                        "lead_score": ai_summary.lead_score_suggested,
                        "sentiment": ai_summary.sentiment.value if ai_summary.sentiment else None,
                        "detected_intent": ai_summary.detected_intent.value if ai_summary.detected_intent else None,
                        "has_property_recommendations": bool(ai_summary.recommended_properties),
                    },
                    ai_generated=True,
                    importance=4,
                )
                
                # Add timeline event for AI insights
                self._add_timeline_event(
                    client_id=attendance.client_id,
                    event_type=TimelineEventType.AI_INSIGHT_GENERATED,
                    title="IA gerou novos insights",
                    description=f"Lead Score: {ai_summary.lead_score_suggested}, Sentimento: {ai_summary.sentiment.value if ai_summary.sentiment else 'N/A'}",
                    related_attendance_id=attendance.id,
                    event_data={
                        "lead_score": ai_summary.lead_score_suggested,
                        "sentiment": ai_summary.sentiment.value if ai_summary.sentiment else None,
                        "confidence": ai_summary.confidence_score,
                        "interest_type": ai_summary.interest_type_detected,
                        "urgency": ai_summary.urgency_level_detected,
                    },
                    ai_generated=True,
                    importance=3,
                )
                
                # Add timeline event for property recommendations if any
                if ai_summary.recommended_properties:
                    self._add_timeline_event(
                        client_id=attendance.client_id,
                        event_type=TimelineEventType.AI_PROPERTY_RECOMMENDED,
                        title=f"IA recomendou {len(ai_summary.recommended_properties)} imóveis",
                        description="Imóveis compatíveis com o perfil do cliente foram identificados",
                        related_attendance_id=attendance.id,
                        event_data={
                            "property_ids": [str(p) for p in ai_summary.recommended_properties],
                            "count": len(ai_summary.recommended_properties),
                        },
                        ai_generated=True,
                        importance=4,
                    )
            else:
                # Even if failed, store error message
                attendance.ai_summary = f"Erro ao gerar resumo: {ai_summary.error_message or 'Erro desconhecido'}"

        except Exception as e:
            # Log error but don't fail attendance update
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error processing completed attendance {attendance.id}: {e}", exc_info=True)
            # Store error in attendance field
            attendance.ai_summary = f"Erro ao processar atendimento completado: {str(e)}"

    def _add_timeline_event(
        self,
        client_id: uuid.UUID,
        event_type: TimelineEventType,
        title: str,
        description: str | None = None,
        related_attendance_id: uuid.UUID | None = None,
        related_visit_id: uuid.UUID | None = None,
        related_property_id: uuid.UUID | None = None,
        event_data: dict | None = None,
        ai_generated: bool = False,
        importance: int = 3,
        auto_add: bool = True,
    ) -> ClientTimeline | None:
        """
        Add a timeline event for the client.
        
        Args:
            client_id: Client UUID
            event_type: Type of event
            title: Event title
            description: Event description
            related_attendance_id: Related attendance ID
            related_visit_id: Related visit ID
            related_property_id: Related property ID
            event_data: Additional event data
            ai_generated: Whether AI generated this event
            importance: Importance level (1-5)
            auto_add: If True, add to session immediately. If False, return event for manual addition.
        
        Returns:
            ClientTimeline event instance (or None if error)
        """
        try:
            event = ClientTimeline(
                client_id=client_id,
                event_type=event_type,
                title=title,
                description=description,
                event_data=event_data,
                related_attendance_id=related_attendance_id,
                related_visit_id=related_visit_id,
                related_property_id=related_property_id,
                ai_generated=ai_generated,
                importance=importance,
            )
            if auto_add:
                self.db.add(event)
            return event
        except Exception as e:
            logger.error(f"Error creating timeline event: {e}", exc_info=True)
            return None

    def _check_objective_completed(
        self,
        attendance: Attendance,
        ai_summary: AISummary,
    ) -> bool:
        """
        Check if the attendance objective was completed (sale finalized).
        
        Args:
            attendance: Attendance instance
            ai_summary: AI summary for the attendance
            
        Returns:
            True if objective was completed, False otherwise
        """
        # Check client status
        client_repo = ClientRepository(self.db)
        client = client_repo.get_by_id(attendance.client_id)
        if client and client.current_status:
            from app.clients.models import ClientStatus
            if client.current_status == ClientStatus.WON:
                return True
        
        # Check if summary text indicates sale completion
        summary_lower = ai_summary.summary_text.lower()
        completion_keywords = [
            "concretizado",
            "concretizada",
            "confirmou a compra",
            "confirmou a venda",
            "negócio foi",
            "venda foi",
            "compra foi",
            "fechou o negócio",
            "fechou negócio",
            "compra confirmada",
            "venda confirmada",
            "negócio fechado",
            "compra realizada",
            "venda realizada",
        ]
        
        if any(keyword in summary_lower for keyword in completion_keywords):
            return True
        
        # Check if there are completed visits related to this attendance
        visit_repo = VisitRepository(self.db)
        visits_stmt = select(Visit).where(Visit.attendance_id == attendance.id)
        visits = list(self.db.scalars(visits_stmt).all())
        if visits:
            completed_visits = [v for v in visits if v.status == VisitStatus.COMPLETED]
            if completed_visits:
                # If there's a completed visit and the summary mentions satisfaction/completion
                satisfaction_keywords = [
                    "adorou",
                    "gostou muito",
                    "satisfeito",
                    "satisfeita",
                    "aprovou",
                    "aceitou",
                    "fechou",
                ]
                if any(keyword in summary_lower for keyword in satisfaction_keywords):
                    return True
        
        return False

    def _generate_ai_summary(self, attendance: Attendance) -> None:
        """
        Generate and save AI summary for attendance.
        
        If an AI summary already exists for this attendance, it will be updated.
        Otherwise, a new one will be created.

        Args:
            attendance: Attendance instance
        """
        try:
            ai_repo = AISummaryRepository(self.db)
            
            # Check if AI summary already exists
            existing_summary = ai_repo.get_by_attendance_id(attendance.id)
            
            # Generate AI summary using AI service
            # Pass db for property recommendations
            ai_data = AISummaryService.generate_summary(attendance, db=self.db)
            
            # Convert recommended_properties UUIDs to strings for JSON serialization
            if ai_data.get('recommended_properties'):
                ai_data['recommended_properties'] = [
                    str(prop_id) if isinstance(prop_id, uuid.UUID) else prop_id
                    for prop_id in ai_data['recommended_properties']
                ]

            if existing_summary:
                # Update existing summary
                from app.ai.schemas import AISummaryUpdate
                summary_update = AISummaryUpdate(
                    summary_text=ai_data.get("summary_text"),
                    key_points=ai_data.get("key_points"),
                    recommended_properties=ai_data.get("recommended_properties"),
                    detected_intent=ai_data.get("detected_intent"),
                    interest_type_detected=ai_data.get("interest_type_detected"),
                    budget_min_detected=ai_data.get("budget_min_detected"),
                    budget_max_detected=ai_data.get("budget_max_detected"),
                    urgency_level_detected=ai_data.get("urgency_level_detected"),
                    lead_score_suggested=ai_data.get("lead_score_suggested"),
                    sentiment=ai_data.get("sentiment"),
                    model_used=ai_data.get("model_used"),
                    prompt_version=ai_data.get("prompt_version"),
                    confidence_score=ai_data.get("confidence_score"),
                    status=ai_data.get("status"),
                    error_message=ai_data.get("error_message"),
                )
                ai_summary = ai_repo.update(existing_summary, summary_update)
            else:
                # Create new AI summary record
                summary_data = AISummaryCreate(
                    attendance_id=attendance.id,
                    client_id=attendance.client_id,
                    **ai_data,
                )
                ai_summary = ai_repo.create(summary_data)

            # Update attendance's ai_summary and ai_next_steps fields for backward compatibility
            status_value = ai_summary.status.value if hasattr(ai_summary.status, 'value') else str(ai_summary.status)
            if status_value == "COMPLETED":
                attendance.ai_summary = ai_summary.summary_text
                
                # Check if objective was completed (sale finalized)
                objective_completed = self._check_objective_completed(
                    attendance=attendance,
                    ai_summary=ai_summary
                )
                
                # Generate next steps based on whether objective was completed
                if objective_completed:
                    # Objective completed - generate post-sale next steps
                    next_steps = [
                        "Finalizar documentação da compra",
                        "Acompanhar processo de escritura",
                        "Agendar assinatura de contrato",
                        "Enviar documentação necessária para o cliente"
                    ]
                else:
                    # Objective not completed - generate regular next steps
                    next_steps = []
                    
                    # Add action based on detected intent
                    if ai_summary.detected_intent:
                        intent_labels = {
                            "PROPERTY_SEARCH": "Buscar propriedades compatíveis com o perfil",
                            "SCHEDULE_VISIT": "Agendar visita para conhecer imóveis",
                            "PRICE_NEGOTIATION": "Negociar valores e condições",
                            "INFORMATION_REQUEST": "Enviar informações detalhadas",
                            "DOCUMENTATION_REQUEST": "Preparar documentação solicitada",
                            "COMPLAINT": "Resolver reclamação apresentada",
                            "GENERAL_INQUIRY": "Acompanhar interesse do cliente",
                        }
                        intent_value = ai_summary.detected_intent.value if hasattr(ai_summary.detected_intent, 'value') else str(ai_summary.detected_intent)
                        intent_label = intent_labels.get(intent_value, "Acompanhar cliente")
                        next_steps.append(intent_label)
                    
                    if ai_summary.interest_type_detected:
                        interest_type_labels = {
                            "BUY": "Comprar imóvel",
                            "RENT": "Alugar imóvel",
                            "SELL": "Vender imóvel",
                            "INVEST": "Investir em imóvel",
                        }
                        interest_type_value = ai_summary.interest_type_detected.value if hasattr(ai_summary.interest_type_detected, 'value') else str(ai_summary.interest_type_detected)
                        interest_label = interest_type_labels.get(interest_type_value, interest_type_value)
                        next_steps.append(f"Cliente interessado em: {interest_label}")
                    
                    if ai_summary.urgency_level_detected:
                        urgency_labels = {
                            "IMMEDIATE": "URGENTE - Contatar imediatamente",
                            "HIGH": "Alta prioridade - Contatar em até 24h",
                            "MEDIUM": "Média prioridade - Contatar em até 3 dias",
                            "LOW": "Baixa prioridade - Contatar em até 7 dias",
                        }
                        urgency_value = ai_summary.urgency_level_detected.value if hasattr(ai_summary.urgency_level_detected, 'value') else str(ai_summary.urgency_level_detected)
                        urgency_label = urgency_labels.get(urgency_value, urgency_value)
                        next_steps.append(urgency_label)
                    
                    if ai_summary.budget_min_detected or ai_summary.budget_max_detected:
                        budget_str = ""
                        if ai_summary.budget_min_detected:
                            budget_str += f"R$ {ai_summary.budget_min_detected:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        if ai_summary.budget_max_detected:
                            if budget_str:
                                budget_str += " - "
                            budget_str += f"R$ {ai_summary.budget_max_detected:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        next_steps.append(f"Orçamento identificado: {budget_str}")
                    
                    if ai_summary.recommended_properties and len(ai_summary.recommended_properties) > 0:
                        next_steps.append(f"Apresentar {len(ai_summary.recommended_properties)} imóvel(eis) recomendado(s)")
                
                if next_steps:
                    attendance.ai_next_steps = "\n".join(f"• {step}" for step in next_steps)
                
                # Update client with AI-detected information GRADUALLY
                # This happens every time an AI summary is generated/updated (not just when attendance is completed)
                # This allows lead_score to increase gradually as more data is collected during the attendance cycle
                # The ClientStateDerivationService uses cluster logic and anti-flip to ensure smooth, incremental updates
                self._update_client_from_ai_summary(attendance.client_id, ai_summary)
            else:
                # Even if failed, store error message
                attendance.ai_summary = f"Erro ao gerar resumo: {ai_summary.error_message or 'Erro desconhecido'}"

        except Exception as e:
            # Log error but don't fail attendance creation
            # Use module-level logger (already defined at top of file)
            # Store attendance_id before accessing attendance (session may be in rollback)
            attendance_id_str = str(attendance.id) if hasattr(attendance, 'id') and attendance.id else "unknown"
            logger.error(f"Error generating AI summary for attendance {attendance_id_str}: {e}", exc_info=True)
            
            # Rollback transaction to clear any pending state
            try:
                self.db.rollback()
            except Exception:
                pass  # Ignore rollback errors
            
            # Store error in attendance field (only if attendance is still attached)
            try:
                if attendance and hasattr(attendance, 'ai_summary'):
                    attendance.ai_summary = f"Erro ao gerar resumo da IA: {str(e)}"
            except Exception:
                pass  # Ignore if attendance is detached

    def _update_client_from_ai_summary(self, client_id: uuid.UUID, ai_summary: AISummary) -> None:
        """
        Update client with information derived from structured signals.
        
        ⚠️ IMPORTANT: This method is called AUTOMATICALLY whenever:
        - A new attendance is created and AI summary is generated
        - An attendance is updated and AI summary is regenerated
        - An attendance is completed and final AI analysis is performed
        
        The system is ALWAYS ATTENTIVE to detect changes:
        - ✅ New conversation → AI analyzes → Detects interest changes → Updates client profile
        - ✅ Conversation update → AI re-analyzes → Detects new information → Updates client profile
        - ✅ Any mention of budget, property type, city, urgency → Automatically detected and applied
        
        This method uses ClientStateDerivationService to:
        - Derive consolidated state from ALL signals (not just this summary)
        - Apply suggestions incrementally (gradual updates, not sudden changes)
        - Respect human-defined values (doesn't overwrite manual inputs)
        - Use cluster logic to avoid mixing contexts (prevents conflicting signals)
        - Detect and apply changes in: interest_type, property_type, city, budget, urgency, lead_score
        
        Args:
            client_id: Client UUID
            ai_summary: AI summary instance (used for context, but derivation considers all signals)
        """
        from app.clients.schemas import ClientUpdate
        from app.clients.models import ClientStatus
        from datetime import datetime

        client_repo = ClientRepository(self.db)
        client = client_repo.get_by_id(client_id)

        if not client:
            return

        # Derive consolidated state from all signals using ClientStateDerivationService
        # This ensures we use cluster logic and respect human values
        derivation_result = ClientStateDerivationService.derive_client_state(
            client_id=client_id,
            db=self.db,
            respect_human_values=True,  # Don't overwrite human-defined values
            only_active_attendances=False,  # Consider all attendances for consolidation
            max_cycles=None,  # Consider all cycles
            use_cluster_logic=True,  # Use cluster logic to avoid mixing contexts
        )
        
        suggestions = derivation_result.get("suggestions", [])
        field_sources = derivation_result.get("field_sources", {})
        signals_count = derivation_result.get("signals_count", 0)
        
        # FALLBACK: If no lead_score suggestion was created but AI summary has lead_score_suggested,
        # create a direct suggestion to ensure lead_score is updated
        if ai_summary.lead_score_suggested is not None:
            has_lead_score_suggestion = any(s.field_name == "current_lead_score" for s in suggestions)
            if not has_lead_score_suggestion:
                from app.clients.state_derivation_service import ClientStateSuggestion
                direct_suggestion = ClientStateSuggestion(
                    field_name="current_lead_score",
                    suggested_value=ai_summary.lead_score_suggested,
                    confidence=ai_summary.confidence_score or 0.8,
                    source_attendance_id=ai_summary.attendance_id,
                    source_ai_summary_id=ai_summary.id,
                    detected_at=ai_summary.created_at,
                    reason=f"Direct AI suggestion from summary {ai_summary.id} (fallback)",
                )
                suggestions.append(direct_suggestion)
        
        if not suggestions:
            # No suggestions to apply, but still update last_contact_at and track derivation
            update_data = {
                "last_contact_at": datetime.utcnow(),
                "last_state_derivation_at": datetime.utcnow(),
                "state_derivation_count": (client.state_derivation_count or 0) + 1,
                "state_derived_from_attendances_count": signals_count,
            }
            client_update = ClientUpdate(**update_data)
            client_repo.update(client, client_update, allow_ai_lead_score_update=False)
            return
        
        # Helper function to convert values to JSON-serializable types
        def json_serializable_value(value):
            """Convert value to JSON-serializable type."""
            from decimal import Decimal
            if value is None:
                return None
            elif isinstance(value, Decimal):
                return float(value)
            elif hasattr(value, 'value'):  # Enum
                return value.value
            return value
        
        # Prepare update data from suggestions
        update_data = {}
        old_values = {}  # Track changes for timeline
        
        for suggestion in suggestions:
            field_name = suggestion.field_name
            current_value = getattr(client, field_name, None)
            
            # For lead_score, always apply (AI-controlled, should always update)
            # For other fields, only apply if value is different
            if field_name == "current_lead_score" or current_value != suggestion.suggested_value:
                old_values[field_name] = json_serializable_value(current_value)
                update_data[field_name] = suggestion.suggested_value
        
        # Update current_status based on detected intent and context (legacy logic for status progression)
        new_status = self._determine_client_status_from_ai(client, ai_summary)
        if new_status and client.current_status != new_status:
            old_values["current_status"] = client.current_status.value if client.current_status else None
            update_data["current_status"] = new_status

        # Always update last_contact_at
        update_data["last_contact_at"] = datetime.utcnow()
        
        # Track state derivation metadata (for visibility/transparency)
        update_data["last_state_derivation_at"] = datetime.utcnow()
        update_data["state_derivation_count"] = (client.state_derivation_count or 0) + 1
        update_data["state_derived_from_attendances_count"] = signals_count

        if update_data:
            client_update = ClientUpdate(**update_data)
            # Allow AI-driven updates from state derivation (all AI-controlled fields)
            updated_client = client_repo.update(
                client, 
                client_update, 
                allow_ai_lead_score_update=True,
                allow_ai_updates=True,  # Allow updates to all AI-controlled fields
            )
            
            # Add timeline event for AI-driven client update
            if old_values:
                changes_description = []
                for field, old_val in old_values.items():
                    new_val = update_data.get(field)
                    field_labels = {
                        "current_interest_type": "Tipo de Interesse",
                        "current_property_type": "Tipo de Imóvel",
                        "current_city_interest": "Cidade de Interesse",
                        "current_budget_min": "Orçamento Mínimo",
                        "current_budget_max": "Orçamento Máximo",
                        "current_urgency_level": "Urgência",
                        "current_lead_score": "Lead Score",
                        "current_status": "Status",
                    }
                    label = field_labels.get(field, field)
                    
                    # Get source information for this field
                    source_info = None
                    for suggestion in suggestions:
                        if suggestion.field_name == field:
                            source_info = {
                                "attendance_id": str(suggestion.source_attendance_id),
                                "confidence": suggestion.confidence,
                                "reason": suggestion.reason,
                            }
                            break
                    
                    change_desc = f"{label}: {old_val or 'N/A'} → {new_val}"
                    if source_info:
                        change_desc += f" (Confiança: {source_info['confidence']:.2f})"
                    changes_description.append(change_desc)
                
                # Convert new_values to JSON-serializable format
                new_values_serializable = {}
                for k, v in update_data.items():
                    if k in old_values:
                        new_values_serializable[k] = json_serializable_value(v)
                
                self._add_timeline_event(
                    client_id=client_id,
                    event_type=TimelineEventType.CLIENT_UPDATED_BY_AI,
                    title="IA atualizou perfil do cliente (derivado de sinais consolidados)",
                    description="; ".join(changes_description),
                    event_data={
                        "old_values": old_values,
                        "new_values": new_values_serializable,
                        "field_sources": field_sources,
                        "signals_count": derivation_result.get("signals_count", 0),
                        "traceability": derivation_result.get("traceability", {}),
                    },
                    ai_generated=True,
                    importance=4,
                )
                
                logger.info(
                    f"Updated client {client_id} from AI summary {ai_summary.id}. "
                    f"Applied {len(suggestions)} suggestions from {derivation_result.get('signals_count', 0)} signals. "
                    f"Fields updated: {list(old_values.keys())}"
                )

    def _determine_client_status_from_ai(self, client, ai_summary: AISummary) -> str | None:
        """
        Determine client status based on AI-detected intent and context.
        
        Status progression logic:
        - NEW_LEAD → CONTACTED (after first attendance)
        - CONTACTED → QUALIFIED (if interest/budget detected)
        - QUALIFIED → VISIT_SCHEDULED (if visit intent detected)
        - Any → NEGOTIATING (if price negotiation detected)
        """
        from app.clients.models import ClientStatus
        
        current = client.current_status
        intent = ai_summary.detected_intent.value if ai_summary.detected_intent else None
        
        # Map of allowed status transitions (from -> list of possible next statuses)
        status_order = {
            ClientStatus.NEW_LEAD: 1,
            ClientStatus.CONTACTED: 2,
            ClientStatus.QUALIFIED: 3,
            ClientStatus.VISIT_SCHEDULED: 4,
            ClientStatus.VISITING: 5,
            ClientStatus.PROPOSAL_SENT: 6,
            ClientStatus.NEGOTIATING: 7,
            ClientStatus.WON: 10,
            ClientStatus.LOST: 10,
            ClientStatus.INACTIVE: 0,
        }
        
        current_order = status_order.get(current, 0)
        
        # If NEW_LEAD and has attendance, move to CONTACTED
        if current == ClientStatus.NEW_LEAD or current is None:
            return ClientStatus.CONTACTED.value
        
        # If CONTACTED and we detected interest type or budget, move to QUALIFIED
        if current == ClientStatus.CONTACTED:
            if ai_summary.interest_type_detected or ai_summary.budget_min_detected or ai_summary.budget_max_detected:
                return ClientStatus.QUALIFIED.value
        
        # If intent is SCHEDULE_VISIT, move to VISIT_SCHEDULED
        if intent == "SCHEDULE_VISIT" and current_order < status_order[ClientStatus.VISIT_SCHEDULED]:
            return ClientStatus.VISIT_SCHEDULED.value
        
        # If intent is PRICE_NEGOTIATION, move to NEGOTIATING
        if intent == "PRICE_NEGOTIATION" and current_order < status_order[ClientStatus.NEGOTIATING]:
            return ClientStatus.NEGOTIATING.value
        
        # If sentiment is very negative or intent is complaint, might indicate risk
        sentiment = ai_summary.sentiment.value if ai_summary.sentiment else None
        if sentiment == "VERY_NEGATIVE" and current_order >= status_order[ClientStatus.NEGOTIATING]:
            # Don't automatically set to LOST, but flag concern
            pass
        
        return None  # No status change

    def _create_visit_from_attendance(self, attendance: Attendance) -> None:
        """
        Create a visit from attendance if scheduled_visit_at is provided.

        Args:
            attendance: Attendance instance
        """
        if not attendance.scheduled_visit_at:
            return

        from app.visits.schemas import VisitCreate

        visit_data = VisitCreate(
            attendance_id=attendance.id,
            property_id=attendance.property_id,
            client_id=attendance.client_id,
            broker_id=attendance.agent_id,
            scheduled_at=attendance.scheduled_visit_at,
            status=VisitStatus.SCHEDULED,
            notes=f"Visita agendada durante atendimento via {attendance.channel.value}",
        )

        visit_repo = VisitRepository(self.db)
        visit_repo.create(visit_data)

    def get_by_id(self, attendance_id: uuid.UUID) -> Attendance | None:
        """
        Get attendance by ID.

        Args:
            attendance_id: Attendance UUID

        Returns:
            Attendance instance or None if not found
        """
        stmt = select(Attendance).where(Attendance.id == attendance_id)
        return self.db.scalar(stmt)

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        client_id: uuid.UUID | None = None,
        agent_id: uuid.UUID | None = None,
        property_id: uuid.UUID | None = None,
        channel: AttendanceChannel | None = None,
        status: AttendanceStatus | None = None,
    ) -> List[Attendance]:
        """
        Get all attendances with optional filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            client_id: Optional filter by client ID
            agent_id: Optional filter by agent ID
            property_id: Optional filter by property ID
            channel: Optional filter by channel
            status: Optional filter by status

        Returns:
            List of attendance instances
        """
        stmt = select(Attendance)

        if client_id:
            stmt = stmt.where(Attendance.client_id == client_id)
        if agent_id:
            stmt = stmt.where(Attendance.agent_id == agent_id)
        if property_id:
            stmt = stmt.where(Attendance.property_id == property_id)
        if channel:
            stmt = stmt.where(Attendance.channel == channel)
        if status:
            stmt = stmt.where(Attendance.status == status)
        stmt = stmt.offset(skip).limit(limit).order_by(Attendance.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def update(
        self,
        attendance: Attendance,
        attendance_data: AttendanceUpdate,
    ) -> Attendance:
        """
        Update attendance information.

        Args:
            attendance: Attendance instance to update
            attendance_data: Update data (only provided fields will be updated)

        Returns:
            Updated attendance instance
        """
        update_data = attendance_data.model_dump(exclude_unset=True)


        # Serialize updated_client_status to JSON string if provided
        if "updated_client_status" in update_data and update_data["updated_client_status"] is not None:
            client_status_update = update_data.pop("updated_client_status")
            update_data["updated_client_status"] = json.dumps(
                client_status_update.model_dump(exclude_unset=True) if hasattr(client_status_update, "model_dump") else client_status_update
            )

        # PROTECTION: Block raw_content updates for closed cycles
        # Once a cycle is closed (COMPLETED, LOST, ABANDONED), no new conversations can be added
        closed_statuses = [AttendanceStatus.COMPLETED, AttendanceStatus.LOST, AttendanceStatus.ABANDONED]
        is_currently_closed = attendance.status in closed_statuses
        
        if "raw_content" in update_data and is_currently_closed:
            logger.warning(
                f"Attempted to update raw_content of closed attendance {attendance.id} "
                f"(status: {attendance.status.value}) for client {attendance.client_id}. "
                "Closed cycles cannot receive new conversations."
            )
            # Remove raw_content from update_data to prevent modification
            update_data.pop("raw_content")
            logger.info(
                f"Removed raw_content from update for closed attendance {attendance.id}. "
                "Other fields will still be updated if provided."
            )

        # Store previous status before update (needed for timeline event)
        previous_status = attendance.status
        
        # Check if status is being changed to COMPLETED, LOST, or ABANDONED
        status_changed_to_completed = (
            "status" in update_data
            and update_data["status"] == AttendanceStatus.COMPLETED
            and attendance.status != AttendanceStatus.COMPLETED
        )
        
        status_changed_to_lost = (
            "status" in update_data
            and update_data["status"] == AttendanceStatus.LOST
            and attendance.status != AttendanceStatus.LOST
        )
        
        status_changed_to_abandoned = (
            "status" in update_data
            and update_data["status"] == AttendanceStatus.ABANDONED
            and attendance.status != AttendanceStatus.ABANDONED
        )
        
        status_changed_to_closed = (
            status_changed_to_completed
            or status_changed_to_lost
            or status_changed_to_abandoned
        )

        # Check if fields that affect AI summary are being updated
        ai_relevant_fields = ["raw_content", "property_id", "client_id"]
        ai_relevant_changed = any(field in update_data for field in ai_relevant_fields)
        
        # If AI-relevant fields changed and attendance is already completed, we need to regenerate AI summary
        should_regen_ai = (
            ai_relevant_changed
            and attendance.status == AttendanceStatus.COMPLETED
            and not status_changed_to_completed
        )

        # Delete existing AI summary if we need to regenerate
        if should_regen_ai:
            ai_repo = AISummaryRepository(self.db)
            existing_ai_summary = ai_repo.get_by_attendance_id(attendance.id)
            if existing_ai_summary:
                ai_repo.delete(existing_ai_summary)
                # Clear AI summary fields in attendance
                attendance.ai_summary = None
                attendance.ai_next_steps = None

        for field, value in update_data.items():
            setattr(attendance, field, value)

        self.db.flush()

        # Process AI summary if status changed to COMPLETED
        if status_changed_to_completed:
            # Trigger AI processing for completed attendance
            self._process_completed_attendance(attendance)
        elif should_regen_ai:
            # Regenerate AI summary if relevant fields changed and attendance is completed
            self._process_completed_attendance(attendance)
        
        # If status changed to closed (COMPLETED, LOST, or ABANDONED), add timeline event
        if status_changed_to_closed:
            new_status = update_data.get("status")
            status_label = {
                AttendanceStatus.COMPLETED: "concluído",
                AttendanceStatus.LOST: "perdido",
                AttendanceStatus.ABANDONED: "abandonado",
            }.get(new_status, "fechado")
            
            self._add_timeline_event(
                client_id=attendance.client_id,
                event_type=TimelineEventType.ATTENDANCE_COMPLETED,
                title=f"Ciclo {status_label}",
                description=f"O ciclo de atendimento foi {status_label}. Nenhuma nova conversa será acumulada neste ciclo.",
                related_attendance_id=attendance.id,
                event_data={
                    "previous_status": previous_status.value if previous_status else None,
                    "new_status": new_status.value if new_status else None,
                },
            )

        # Update client status if provided
        if attendance_data.updated_client_status:
            self._update_client_from_attendance(attendance, attendance_data.updated_client_status)

        # Create visit if scheduled_visit_at is provided and not already created
        if attendance_data.scheduled_visit_at and not attendance.scheduled_visit_at:
            self._create_visit_from_attendance(attendance)

        self.db.commit()
        self.db.refresh(attendance)
        return attendance

    def delete(self, attendance: Attendance) -> None:
        """
        Delete an attendance and all related AI summaries.

        Args:
            attendance: Attendance instance to delete
        """
        # Delete related AI summaries first (CASCADE should handle this, but being explicit)
        ai_repo = AISummaryRepository(self.db)
        ai_summary = ai_repo.get_by_attendance_id(attendance.id)
        if ai_summary:
            ai_repo.delete(ai_summary)
        
        # Delete the attendance
        self.db.delete(attendance)
        self.db.commit()

