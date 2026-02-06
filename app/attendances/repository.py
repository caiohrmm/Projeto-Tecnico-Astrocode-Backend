"""Attendance repository for database operations."""

import json
import uuid
from datetime import datetime
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.attendances.models import Attendance, AttendanceChannel, AttendanceStatus
from app.attendances.schemas import AttendanceCreate, AttendanceUpdate
from app.ai.models import AISummary
from app.ai.repository import AISummaryRepository
from app.ai.schemas import AISummaryCreate
from app.ai.service import AISummaryService
from app.clients.models import Client
from app.clients.repository import ClientRepository
from app.clients.score_service import LeadScoreService
from app.clients.schemas import ClientUpdate
from app.visits.models import Visit, VisitStatus
from app.visits.repository import VisitRepository


class AttendanceRepository:
    """Repository for attendance database operations."""

    def __init__(self, db: Session) -> None:
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def _calculate_duration(self, started_at: datetime, ended_at: datetime | None) -> int | None:
        """
        Calculate duration in seconds.

        Args:
            started_at: Start datetime
            ended_at: End datetime (nullable)

        Returns:
            Duration in seconds or None if ended_at is None
        """
        if ended_at is None:
            return None
        return int((ended_at - started_at).total_seconds())

    def create(self, attendance_data: AttendanceCreate) -> Attendance:
        """
        Create a new attendance.

        Args:
            attendance_data: Attendance creation data

        Returns:
            Created attendance instance
        """
        attendance_dict = attendance_data.model_dump(exclude_unset=False)

        # Set default status if not provided
        if "status" not in attendance_dict or attendance_dict["status"] is None:
            attendance_dict["status"] = AttendanceStatus.IN_PROGRESS

        # Calculate duration if ended_at is provided
        started_at = attendance_dict.get("started_at")
        ended_at = attendance_dict.get("ended_at")
        if started_at and ended_at:
            attendance_dict["duration"] = self._calculate_duration(started_at, ended_at)

        # Serialize updated_client_status to JSON string if provided
        if "updated_client_status" in attendance_dict and attendance_dict["updated_client_status"] is not None:
            client_status_update = attendance_dict.pop("updated_client_status")
            attendance_dict["updated_client_status"] = json.dumps(
                client_status_update.model_dump(exclude_unset=True) if hasattr(client_status_update, "model_dump") else client_status_update
            )

        db_attendance = Attendance(**attendance_dict)
        self.db.add(db_attendance)
        self.db.flush()  # Flush to get the attendance ID

        # Generate AI summary automatically
        self._generate_ai_summary(db_attendance)

        # Update client status if provided
        if attendance_data.updated_client_status:
            self._update_client_from_attendance(db_attendance, attendance_data.updated_client_status)

        # Create visit if scheduled_visit_at is provided
        if attendance_data.scheduled_visit_at:
            self._create_visit_from_attendance(db_attendance)

        self.db.commit()
        self.db.refresh(db_attendance)
        return db_attendance

    def _update_client_from_attendance(
        self,
        attendance: Attendance,
        client_status_update,
    ) -> None:
        """
        Update client status fields from attendance.

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
        update_data = {}
        if client_status_update.current_status:
            update_data["current_status"] = client_status_update.current_status
        if client_status_update.current_interest_type:
            update_data["current_interest_type"] = client_status_update.current_interest_type
        if client_status_update.current_property_type:
            update_data["current_property_type"] = client_status_update.current_property_type

        if update_data:
            client_update = ClientUpdate(**update_data)
            client_repo.update(client, client_update)

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
                        "FOLLOW_UP": "Fazer follow-up",
                    }
                    intent_label = intent_labels.get(ai_summary.detected_intent.value, "Acompanhar cliente")
                    next_steps.append(intent_label)

                if ai_summary.interest_type_detected:
                    next_steps.append(f"Tipo de interesse: {ai_summary.interest_type_detected}")
                
                if ai_summary.urgency_level_detected:
                    urgency_labels = {
                        "IMMEDIATE": "URGENTE - Contatar imediatamente",
                        "HIGH": "Alta prioridade - Contatar em até 24h",
                        "MEDIUM": "Média prioridade - Contatar em até 3 dias",
                        "LOW": "Baixa prioridade - Contatar em até 7 dias",
                    }
                    urgency_label = urgency_labels.get(ai_summary.urgency_level_detected, ai_summary.urgency_level_detected)
                    next_steps.append(f"Urgência: {urgency_label}")

                if ai_summary.recommended_properties:
                    next_steps.append(f"Recomendar {len(ai_summary.recommended_properties)} propriedade(s) encontrada(s)")

                if next_steps:
                    attendance.ai_next_steps = "\n".join(f"• {step}" for step in next_steps)

                # Update client with AI-detected information
                self._update_client_from_ai_summary(attendance.client_id, ai_summary)
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

    def _generate_ai_summary(self, attendance: Attendance) -> None:
        """
        Generate and save AI summary for attendance (legacy method for creation).

        This method is called when creating a new attendance.
        For completed attendances, use _process_completed_attendance instead.

        Args:
            attendance: Attendance instance
        """
        try:
            # Generate AI summary using AI service (without recommendations for new attendances)
            # Pass None for db to skip property recommendations
            ai_data = AISummaryService.generate_summary(attendance, db=None)

            # Create AI summary record
            summary_data = AISummaryCreate(
                attendance_id=attendance.id,
                client_id=attendance.client_id,
                **ai_data,
            )

            ai_repo = AISummaryRepository(self.db)
            ai_summary = ai_repo.create(summary_data)

            # Update attendance's ai_summary and ai_next_steps fields for backward compatibility
            if ai_summary.status.value == "COMPLETED":
                attendance.ai_summary = ai_summary.summary_text
                # Generate next steps from key points if available
                if ai_summary.key_points:
                    next_steps = []
                    if ai_summary.interest_type_detected:
                        next_steps.append(f"Tipo de interesse detectado: {ai_summary.interest_type_detected}")
                    if ai_summary.urgency_level_detected:
                        next_steps.append(f"Urgência: {ai_summary.urgency_level_detected}")
                    if ai_summary.budget_min_detected or ai_summary.budget_max_detected:
                        budget_str = ""
                        if ai_summary.budget_min_detected:
                            budget_str += f"R$ {ai_summary.budget_min_detected:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        if ai_summary.budget_max_detected:
                            if budget_str:
                                budget_str += " - "
                            budget_str += f"R$ {ai_summary.budget_max_detected:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        next_steps.append(f"Orçamento: {budget_str}")
                    if next_steps:
                        attendance.ai_next_steps = "\n".join(next_steps)
                
                # Update client with AI-detected information
                self._update_client_from_ai_summary(attendance.client_id, ai_summary)
            else:
                # Even if failed, store error message
                attendance.ai_summary = f"Erro ao gerar resumo: {ai_summary.error_message or 'Erro desconhecido'}"

        except Exception as e:
            # Log error but don't fail attendance creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating AI summary for attendance {attendance.id}: {e}", exc_info=True)
            # Store error in attendance field
            attendance.ai_summary = f"Erro ao gerar resumo da IA: {str(e)}"

    def _update_client_from_ai_summary(self, client_id: uuid.UUID, ai_summary: AISummary) -> None:
        """
        Update client with information detected by AI summary.

        This method applies AI-detected information to the client record.
        It respects existing values and only updates when AI provides new information.

        Args:
            client_id: Client UUID
            ai_summary: AI summary instance
        """
        from app.clients.schemas import ClientUpdate
        from datetime import datetime

        client_repo = ClientRepository(self.db)
        client = client_repo.get_by_id(client_id)

        if not client:
            return

        # Prepare update data from AI summary
        update_data = {}

        # Update interest type if detected and not already set
        if ai_summary.interest_type_detected and not client.current_interest_type:
            update_data["current_interest_type"] = ai_summary.interest_type_detected

        # Update property type if detected in key_points
        if ai_summary.key_points and isinstance(ai_summary.key_points, dict):
            detected_prop_type = ai_summary.key_points.get("property_type")
            if detected_prop_type and not client.current_property_type:
                update_data["current_property_type"] = detected_prop_type

        # Update city interest if detected in key_points
        if ai_summary.key_points and isinstance(ai_summary.key_points, dict):
            detected_city = ai_summary.key_points.get("city")
            if detected_city and not client.current_city_interest:
                update_data["current_city_interest"] = detected_city

        # Update budget if detected (only if not already set or AI provides more specific range)
        if ai_summary.budget_min_detected:
            if not client.current_budget_min or ai_summary.budget_min_detected > client.current_budget_min:
                update_data["current_budget_min"] = ai_summary.budget_min_detected
        if ai_summary.budget_max_detected:
            if not client.current_budget_max or ai_summary.budget_max_detected < client.current_budget_max:
                update_data["current_budget_max"] = ai_summary.budget_max_detected

        # Update urgency level if detected and higher than current
        if ai_summary.urgency_level_detected:
            urgency_order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "IMMEDIATE": 4}
            current_urgency_value = urgency_order.get(client.current_urgency_level or "LOW", 0)
            new_urgency_value = urgency_order.get(ai_summary.urgency_level_detected, 0)
            if new_urgency_value > current_urgency_value:
                update_data["current_urgency_level"] = ai_summary.urgency_level_detected

        # Update lead score if suggested (use AI suggestion if higher than current)
        if ai_summary.lead_score_suggested is not None:
            current_score = client.current_lead_score or 0
            if ai_summary.lead_score_suggested > current_score:
                # AI suggestion will be recalculated by LeadScoreService, but we can use it as reference
                # The actual score will be recalculated based on all factors
                pass  # Lead score is recalculated automatically in ClientRepository.update

        # Update last_contact_at
        update_data["last_contact_at"] = datetime.utcnow()

        if update_data:
            client_update = ClientUpdate(**update_data)
            client_repo.update(client, client_update)

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
        started_from: datetime | None = None,
        started_to: datetime | None = None,
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
            started_from: Optional filter by started date (from)
            started_to: Optional filter by started date (to)

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
        if started_from:
            stmt = stmt.where(Attendance.started_at >= started_from)
        if started_to:
            stmt = stmt.where(Attendance.started_at <= started_to)

        stmt = stmt.offset(skip).limit(limit).order_by(Attendance.started_at.desc())
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

        # Validate dates if both are being updated or if ended_at is being updated
        if "ended_at" in update_data or "started_at" in update_data:
            # Get the dates (use updated value if provided, otherwise use existing)
            started_at = update_data.get("started_at", attendance.started_at)
            ended_at = update_data.get("ended_at", attendance.ended_at)
            
            # Validate that ended_at is not before started_at
            if ended_at is not None and started_at is not None:
                if ended_at < started_at:
                    raise ValueError("ended_at cannot be before started_at")
            
            # Recalculate duration if ended_at is being updated
            if "ended_at" in update_data:
                update_data["duration"] = self._calculate_duration(started_at, ended_at)

        # Serialize updated_client_status to JSON string if provided
        if "updated_client_status" in update_data and update_data["updated_client_status"] is not None:
            client_status_update = update_data.pop("updated_client_status")
            update_data["updated_client_status"] = json.dumps(
                client_status_update.model_dump(exclude_unset=True) if hasattr(client_status_update, "model_dump") else client_status_update
            )

        # Check if status is being changed to COMPLETED
        status_changed_to_completed = (
            "status" in update_data
            and update_data["status"] == AttendanceStatus.COMPLETED
            and attendance.status != AttendanceStatus.COMPLETED
        )

        # Check if fields that affect AI summary are being updated
        ai_relevant_fields = ["raw_content", "started_at", "ended_at", "property_id", "client_id"]
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
            # Ensure ended_at is set if not provided
            if not attendance.ended_at:
                from datetime import datetime
                attendance.ended_at = datetime.utcnow()
                attendance.duration = self._calculate_duration(attendance.started_at, attendance.ended_at)
                self.db.flush()

            # Trigger AI processing for completed attendance
            self._process_completed_attendance(attendance)
        elif should_regen_ai:
            # Regenerate AI summary if relevant fields changed and attendance is completed
            self._process_completed_attendance(attendance)

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

