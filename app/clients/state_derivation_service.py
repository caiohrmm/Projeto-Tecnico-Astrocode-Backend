"""Service for deriving consolidated client state from structured signals."""

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.models import AISummary, AISummaryStatus
from app.attendances.models import Attendance, AttendanceStatus
from app.clients.models import (
    Client,
    ClientStatus,
    InterestType,
    PropertyType,
    UrgencyLevel,
)

logger = logging.getLogger(__name__)


class StructuredSignal(BaseModel):
    """
    Structured signal extracted from an AI Summary.
    
    Represents a single piece of information detected from an attendance,
    with metadata for traceability and confidence.
    """
    
    # Signal value
    interest_type: Optional[InterestType] = None
    property_type: Optional[PropertyType] = None
    city: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    urgency_level: Optional[UrgencyLevel] = None
    lead_score: Optional[int] = None
    
    # Metadata for traceability
    source_attendance_id: uuid.UUID
    source_ai_summary_id: uuid.UUID
    detected_at: datetime
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    
    # Additional context
    detected_intent: Optional[str] = None
    sentiment: Optional[str] = None
    
    # Attendance status (for filtering)
    attendance_status: Optional[str] = None  # ACTIVE, COMPLETED, LOST, ABANDONED


class ClientStateSuggestion(BaseModel):
    """
    Suggested client state update derived from structured signals.
    
    Contains the suggested value and traceability information.
    """
    
    field_name: str
    suggested_value: Any
    source_attendance_id: uuid.UUID
    source_ai_summary_id: uuid.UUID
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str  # Why this value was suggested
    detected_at: datetime


class ClientStateDerivationService:
    """
    Service for deriving consolidated client state from structured signals.
    
    This service:
    - Extracts structured signals from AI Summaries across multiple Attendances
    - Consolidates signals using rules (most recent, highest confidence, etc.)
    - Provides traceability (which Attendance generated each value)
    - Respects human-defined values (doesn't overwrite explicit human input)
    - Suggests incremental updates rather than blindly applying
    """
    
    # Minimum confidence threshold for signals to be considered
    MIN_CONFIDENCE_THRESHOLD = 0.5
    
    # Weight factors for signal prioritization
    RECENCY_WEIGHT = 0.4  # More recent signals are more valuable
    CONFIDENCE_WEIGHT = 0.6  # Higher confidence signals are more valuable
    
    # Anti-flip (oscillation control) thresholds
    MIN_CLUSTER_SCORE_DIFFERENCE = 0.15  # New cluster must be at least 0.15 points better to replace current
    MIN_FIELD_SCORE_DIFFERENCE = 0.10  # New field value must be at least 0.10 points better to replace current
    
    @staticmethod
    def extract_signals_from_ai_summary(
        ai_summary: AISummary,
        attendance: Optional[Attendance] = None,
    ) -> Optional[StructuredSignal]:
        """
        Extract structured signals from an AI Summary.
        
        Args:
            ai_summary: AI Summary instance
            attendance: Optional Attendance instance (for status filtering)
            
        Returns:
            StructuredSignal or None if summary is not valid
        """
        # Only process completed summaries
        if ai_summary.status != AISummaryStatus.COMPLETED:
            return None
        
        # Extract city from key_points if available
        city = None
        if ai_summary.key_points and isinstance(ai_summary.key_points, dict):
            city = ai_summary.key_points.get("city")
        
        # Parse interest_type
        interest_type = None
        if ai_summary.interest_type_detected:
            try:
                interest_type = InterestType(ai_summary.interest_type_detected)
            except (ValueError, TypeError):
                pass
        
        # Parse property_type from key_points
        property_type = None
        if ai_summary.key_points and isinstance(ai_summary.key_points, dict):
            prop_type_str = ai_summary.key_points.get("property_type")
            if prop_type_str:
                try:
                    property_type = PropertyType(prop_type_str)
                except (ValueError, TypeError):
                    pass
        
        # Parse urgency_level
        urgency_level = None
        if ai_summary.urgency_level_detected:
            try:
                urgency_level = UrgencyLevel(ai_summary.urgency_level_detected)
            except (ValueError, TypeError):
                pass
        
        # Get attendance status if available
        attendance_status = None
        if attendance:
            attendance_status = attendance.status.value if attendance.status else None
        
        return StructuredSignal(
            interest_type=interest_type,
            property_type=property_type,
            city=city,
            budget_min=ai_summary.budget_min_detected,
            budget_max=ai_summary.budget_max_detected,
            urgency_level=urgency_level,
            lead_score=ai_summary.lead_score_suggested,
            source_attendance_id=ai_summary.attendance_id,
            source_ai_summary_id=ai_summary.id,
            detected_at=ai_summary.created_at,
            confidence_score=ai_summary.confidence_score or 0.0,
            detected_intent=ai_summary.detected_intent.value if ai_summary.detected_intent else None,
            sentiment=ai_summary.sentiment.value if ai_summary.sentiment else None,
            attendance_status=attendance_status,
        )
    
    @staticmethod
    def get_all_signals_for_client(
        client_id: uuid.UUID,
        db: Session,
        only_active_attendances: bool = False,
        max_cycles: Optional[int] = None,
        exclude_if_won: bool = True,
    ) -> list[StructuredSignal]:
        """
        Get all structured signals from AI Summaries for a client.
        
        Args:
            client_id: Client UUID
            db: Database session
            only_active_attendances: If True, only include signals from ACTIVE attendances
            max_cycles: If set, only include signals from the most recent N attendances
            exclude_if_won: If True and client status is WON, exclude old signals
            
        Returns:
            List of structured signals, ordered by detection time (most recent first)
        """
        # Get client to check status
        from app.clients.repository import ClientRepository
        client_repo = ClientRepository(db)
        client = client_repo.get_by_id(client_id)
        
        # Build query
        stmt = (
            select(AISummary)
            .where(AISummary.client_id == client_id)
            .where(AISummary.status == AISummaryStatus.COMPLETED)
            .order_by(AISummary.created_at.desc())
        )
        
        # Filter by attendance status if requested
        if only_active_attendances:
            stmt = stmt.join(Attendance).where(Attendance.status == AttendanceStatus.ACTIVE)
        
        # Limit to most recent N cycles if requested
        if max_cycles:
            stmt = stmt.limit(max_cycles)
        
        ai_summaries = list(db.scalars(stmt).all())
        
        # If client won and exclude_if_won, filter out old signals
        if exclude_if_won and client and client.current_status == ClientStatus.WON:
            # Only keep signals from the last 30 days (recent activity)
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            ai_summaries = [
                s for s in ai_summaries
                if s.created_at.replace(tzinfo=None) >= cutoff_date
            ]
        
        # Extract signals with attendance context
        signals = []
        for ai_summary in ai_summaries:
            # Get attendance for status
            attendance_stmt = select(Attendance).where(Attendance.id == ai_summary.attendance_id)
            attendance = db.scalar(attendance_stmt)
            
            signal = ClientStateDerivationService.extract_signals_from_ai_summary(
                ai_summary,
                attendance=attendance,
            )
            if signal:
                signals.append(signal)
        
        return signals
    
    @staticmethod
    def _calculate_signal_score(
        signal: StructuredSignal,
        reference_time: datetime,
    ) -> float:
        """
        Calculate a score for a signal based on recency and confidence.
        
        Args:
            signal: Structured signal
            reference_time: Reference time for recency calculation
            
        Returns:
            Score (0.0-1.0) for signal prioritization
        """
        # Recency component (0.0-1.0)
        # Signals older than 90 days get lower score
        days_old = (reference_time - signal.detected_at.replace(tzinfo=None)).days
        recency_score = max(0.0, 1.0 - (days_old / 90.0))
        
        # Confidence component (0.0-1.0)
        confidence_score = signal.confidence_score
        
        # Weighted combination
        total_score = (
            recency_score * ClientStateDerivationService.RECENCY_WEIGHT +
            confidence_score * ClientStateDerivationService.CONFIDENCE_WEIGHT
        )
        
        return total_score
    
    @staticmethod
    def derive_state_suggestions(
        client: Client,
        signals: list[StructuredSignal],
        use_cluster_logic: bool = True,
    ) -> list[ClientStateSuggestion]:
        """
        Derive state suggestions from structured signals.
        
        Applies consolidation rules with cluster logic:
        - Groups signals by Attendance (logical cluster)
        - Selects best complete cluster to avoid mixing fields from different contexts
        - Most recent and highest confidence clusters are prioritized
        - Only suggests updates if signal is better than current value
        - Provides traceability for each suggestion
        
        Args:
            client: Client instance
            signals: List of structured signals
            use_cluster_logic: If True, groups by Attendance to avoid mixing contexts
            
        Returns:
            List of state suggestions
        """
        if not signals:
            return []
        
        suggestions = []
        reference_time = datetime.utcnow()
        
        # Filter by minimum confidence
        valid_signals = [
            s for s in signals
            if s.confidence_score >= ClientStateDerivationService.MIN_CONFIDENCE_THRESHOLD
        ]
        
        if not valid_signals:
            return []
        
        if use_cluster_logic:
            # Group signals by Attendance (logical cluster)
            # This ensures we don't mix interest_type from one attendance with city from another
            clusters_by_attendance: dict[uuid.UUID, list[StructuredSignal]] = defaultdict(list)
            for signal in valid_signals:
                clusters_by_attendance[signal.source_attendance_id].append(signal)
            
            # Calculate cluster scores
            cluster_scores = []
            for attendance_id, cluster_signals in clusters_by_attendance.items():
                # Calculate average score for the cluster
                cluster_score = sum(
                    ClientStateDerivationService._calculate_signal_score(s, reference_time)
                    for s in cluster_signals
                ) / len(cluster_signals) if cluster_signals else 0.0
                
                # Boost score if cluster has complete information (interest_type + city + property_type)
                completeness_bonus = 0.0
                has_interest = any(s.interest_type for s in cluster_signals)
                has_city = any(s.city for s in cluster_signals)
                has_property = any(s.property_type for s in cluster_signals)
                
                if has_interest and has_city:
                    completeness_bonus = 0.1
                if has_interest and has_city and has_property:
                    completeness_bonus = 0.2
                
                cluster_scores.append((
                    attendance_id,
                    cluster_signals,
                    cluster_score + completeness_bonus,
                ))
            
            # Sort clusters by score (best first)
            cluster_scores.sort(key=lambda x: x[2], reverse=True)
            
            # Identify current active cluster (based on client's current values)
            current_cluster_score = ClientStateDerivationService._calculate_current_cluster_score(
                client=client,
                signals=valid_signals,
                reference_time=reference_time,
            )
            
            # Use the best cluster for suggestions, but only if it's significantly better
            if cluster_scores:
                best_attendance_id, best_cluster_signals, best_cluster_score = cluster_scores[0]
                
                # Anti-flip: Only suggest changes if new cluster is significantly better
                score_difference = best_cluster_score - current_cluster_score
                
                if score_difference >= ClientStateDerivationService.MIN_CLUSTER_SCORE_DIFFERENCE:
                    # New cluster is significantly better, extract suggestions
                    for signal in best_cluster_signals:
                        suggestion = ClientStateDerivationService._create_suggestion_from_signal(
                            client=client,
                            signal=signal,
                            reference_time=reference_time,
                            cluster_context=True,
                            cluster_size=len(best_cluster_signals),
                            current_cluster_score=current_cluster_score,
                            new_cluster_score=best_cluster_score,
                        )
                        if suggestion:
                            suggestions.append(suggestion)
                else:
                    # New cluster is not significantly better, keep current state
                    logger.info(
                        f"Cluster score difference ({score_difference:.3f}) below threshold "
                        f"({ClientStateDerivationService.MIN_CLUSTER_SCORE_DIFFERENCE}). "
                        f"Keeping current client state to avoid oscillation. "
                        f"Current: {current_cluster_score:.3f}, New: {best_cluster_score:.3f}"
                    )
        else:
            # Fallback: original field-by-field logic (for backward compatibility)
            field_signals = {
                "interest_type": [],
                "property_type": [],
                "city": [],
                "budget_min": [],
                "budget_max": [],
                "urgency_level": [],
                "lead_score": [],
            }
            
            for signal in valid_signals:
                if signal.interest_type:
                    field_signals["interest_type"].append(signal)
                if signal.property_type:
                    field_signals["property_type"].append(signal)
                if signal.city:
                    field_signals["city"].append(signal)
                if signal.budget_min is not None:
                    field_signals["budget_min"].append(signal)
                if signal.budget_max is not None:
                    field_signals["budget_max"].append(signal)
                if signal.urgency_level:
                    field_signals["urgency_level"].append(signal)
                if signal.lead_score is not None:
                    field_signals["lead_score"].append(signal)
            
            # Process each field
            for field_name, field_signal_list in field_signals.items():
                if not field_signal_list:
                    continue
                
                # Map field name to client field name
                client_field_name = field_name
                if field_name == "city":
                    client_field_name = "city_interest"
                
                # Sort by score (best first)
                scored_signals = [
                    (signal, ClientStateDerivationService._calculate_signal_score(signal, reference_time))
                    for signal in field_signal_list
                ]
                scored_signals.sort(key=lambda x: x[1], reverse=True)
                
                best_signal, best_score = scored_signals[0]
                
                # Anti-flip: Calculate current field score
                current_value = getattr(client, f"current_{client_field_name}", None)
                current_field_score = 0.0
                if current_value is not None:
                    # Find signal that matches current value
                    for signal in field_signal_list:
                        signal_value = None
                        if field_name == "interest_type":
                            signal_value = signal.interest_type
                        elif field_name == "property_type":
                            signal_value = signal.property_type
                        elif field_name == "city":
                            signal_value = signal.city
                        elif field_name == "budget_min":
                            signal_value = signal.budget_min
                        elif field_name == "budget_max":
                            signal_value = signal.budget_max
                        elif field_name == "urgency_level":
                            signal_value = signal.urgency_level
                        elif field_name == "lead_score":
                            signal_value = signal.lead_score
                        
                        if signal_value == current_value:
                            current_field_score = ClientStateDerivationService._calculate_signal_score(
                                signal, reference_time
                            )
                            break
                
                # Only suggest if new value is significantly better
                score_difference = best_score - current_field_score
                
                if score_difference >= ClientStateDerivationService.MIN_FIELD_SCORE_DIFFERENCE:
                    suggestion = ClientStateDerivationService._create_suggestion_from_signal(
                        client=client,
                        signal=best_signal,
                        reference_time=reference_time,
                        field_name=client_field_name,
                        cluster_context=False,
                    )
                    if suggestion:
                        suggestions.append(suggestion)
                else:
                    logger.debug(
                        f"Field {field_name} score difference ({score_difference:.3f}) below threshold "
                        f"({ClientStateDerivationService.MIN_FIELD_SCORE_DIFFERENCE}). "
                        f"Keeping current value to avoid oscillation."
                    )
        
        return suggestions
    
    @staticmethod
    def _calculate_current_cluster_score(
        client: Client,
        signals: list[StructuredSignal],
        reference_time: datetime,
    ) -> float:
        """
        Calculate score for the cluster that matches client's current values.
        
        This is used for anti-flip logic: we only change if new cluster is significantly better.
        
        Args:
            client: Client instance
            signals: List of all signals
            reference_time: Reference time for recency calculation
            
        Returns:
            Score of the current cluster (0.0 if no matching cluster found)
        """
        # Find signals that match current client values (current cluster)
        matching_signals = []
        
        for signal in signals:
            matches = True
            
            # Check if signal matches current client state
            if client.current_interest_type:
                if not signal.interest_type or signal.interest_type != client.current_interest_type:
                    matches = False
            
            if client.current_city_interest:
                if not signal.city or signal.city.lower() != client.current_city_interest.lower():
                    matches = False
            
            if client.current_property_type:
                if not signal.property_type or signal.property_type != client.current_property_type:
                    matches = False
            
            if matches:
                matching_signals.append(signal)
        
        if not matching_signals:
            # No matching cluster found, return low score (easy to replace)
            return 0.0
        
        # Calculate average score for matching signals
        current_score = sum(
            ClientStateDerivationService._calculate_signal_score(s, reference_time)
            for s in matching_signals
        ) / len(matching_signals) if matching_signals else 0.0
        
        # Add completeness bonus if current cluster has complete info
        has_interest = client.current_interest_type is not None
        has_city = client.current_city_interest is not None
        has_property = client.current_property_type is not None
        
        completeness_bonus = 0.0
        if has_interest and has_city:
            completeness_bonus = 0.1
        if has_interest and has_city and has_property:
            completeness_bonus = 0.2
        
        return current_score + completeness_bonus
    
    @staticmethod
    def _create_suggestion_from_signal(
        client: Client,
        signal: StructuredSignal,
        reference_time: datetime,
        field_name: Optional[str] = None,
        cluster_context: bool = False,
        cluster_size: int = 1,
        current_cluster_score: Optional[float] = None,
        new_cluster_score: Optional[float] = None,
    ) -> Optional[ClientStateSuggestion]:
        """
        Create a suggestion from a signal.
        
        Args:
            client: Client instance
            signal: Structured signal
            reference_time: Reference time for recency calculation
            field_name: Specific field name (if None, auto-detect from signal)
            cluster_context: If True, signal is from a cluster
            cluster_size: Size of the cluster (for reason building)
            
        Returns:
            ClientStateSuggestion or None if no suggestion needed
        """
        # Auto-detect field name if not provided
        if not field_name:
            if signal.interest_type:
                field_name = "interest_type"
                suggested_value = signal.interest_type
            elif signal.property_type:
                field_name = "property_type"
                suggested_value = signal.property_type
            elif signal.city:
                field_name = "city_interest"  # Map to client field name
                suggested_value = signal.city
            elif signal.budget_min is not None:
                field_name = "budget_min"
                suggested_value = Decimal(str(signal.budget_min))
            elif signal.budget_max is not None:
                field_name = "budget_max"
                suggested_value = Decimal(str(signal.budget_max))
            elif signal.urgency_level:
                field_name = "urgency_level"
                suggested_value = signal.urgency_level
            elif signal.lead_score is not None:
                field_name = "lead_score"
                suggested_value = signal.lead_score
            else:
                return None
        else:
            # Extract value based on field name
            if field_name == "interest_type":
                suggested_value = signal.interest_type
            elif field_name == "property_type":
                suggested_value = signal.property_type
            elif field_name == "city" or field_name == "city_interest":
                suggested_value = signal.city
                field_name = "city_interest"  # Normalize to client field name
            elif field_name == "budget_min":
                suggested_value = Decimal(str(signal.budget_min)) if signal.budget_min else None
            elif field_name == "budget_max":
                suggested_value = Decimal(str(signal.budget_max)) if signal.budget_max else None
            elif field_name == "urgency_level":
                suggested_value = signal.urgency_level
            elif field_name == "lead_score":
                suggested_value = signal.lead_score
            else:
                return None
        
        if suggested_value is None:
            return None
        
        # Extract current value
        current_value = getattr(client, f"current_{field_name}", None)
        
        # Only suggest if value is different
        if current_value == suggested_value:
            return None
        
        # Build reason
        reason_parts = []
        if signal.confidence_score >= 0.8:
            reason_parts.append("alta confiança")
        if (reference_time - signal.detected_at.replace(tzinfo=None)).days <= 7:
            reason_parts.append("sinal recente")
        if cluster_context:
            reason_parts.append(f"cluster completo ({cluster_size} sinais)")
            if current_cluster_score is not None and new_cluster_score is not None:
                score_diff = new_cluster_score - current_cluster_score
                reason_parts.append(f"score +{score_diff:.2f} vs atual")
        else:
            reason_parts.append("sinal válido")
        
        reason = f"Detectado por IA ({', '.join(reason_parts)})"
        
        return ClientStateSuggestion(
            field_name=f"current_{field_name}",
            suggested_value=suggested_value,
            source_attendance_id=signal.source_attendance_id,
            source_ai_summary_id=signal.source_ai_summary_id,
            confidence=signal.confidence_score,
            reason=reason,
            detected_at=signal.detected_at,
        )
    
    @staticmethod
    def _is_field_manually_set(
        client: Client,
        field_name: str,
        db: Session,
    ) -> bool:
        """
        Heuristic to determine if a field was manually set by a human.
        
        Current heuristic:
        - Check timeline events for AI updates
        - If field was updated via AI timeline event recently, consider it AI-set
        - Otherwise, assume it might be manually set if it has a value
        
        TODO: Future improvement - add field_source tracking to Client model:
        - Add JSONB field: field_sources = {"current_interest_type": "HUMAN", "current_city": "AI", ...}
        - HUMAN: Explicitly set by human
        - AI: Set by AI derivation
        - MIXED: Both human and AI have contributed
        
        Args:
            client: Client instance
            field_name: Field name to check (e.g., "current_interest_type")
            db: Database session
            
        Returns:
            True if field appears to be manually set, False otherwise
        """
        from app.clients.timeline_models import ClientTimeline, TimelineEventType
        
        current_value = getattr(client, field_name, None)
        if current_value is None:
            return False  # Not set, so not manually set
        
        # Check if there's a recent AI update event for this client
        # If AI updated recently, assume field is AI-set
        stmt = (
            select(ClientTimeline)
            .where(ClientTimeline.client_id == client.id)
            .where(ClientTimeline.event_type == TimelineEventType.CLIENT_UPDATED_BY_AI)
            .where(ClientTimeline.ai_generated == True)
            .order_by(ClientTimeline.created_at.desc())
            .limit(10)  # Check last 10 AI update events
        )
        
        ai_update_events = list(db.scalars(stmt).all())
        
        # Check if any AI event updated this field
        for event in ai_update_events:
            if event.event_data and isinstance(event.event_data, dict):
                new_values = event.event_data.get("new_values", {})
                if field_name in new_values:
                    # AI updated this field, so it's not manually set
                    return False
        
        # If field has value but no AI update event found, assume it might be manually set
        # Conservative approach: if we can't prove it's AI-set, assume it's manually set
        return True
    
    @staticmethod
    def derive_client_state(
        client_id: uuid.UUID,
        db: Session,
        respect_human_values: bool = True,
        only_active_attendances: bool = False,
        max_cycles: Optional[int] = None,
        use_cluster_logic: bool = True,
    ) -> dict[str, Any]:
        """
        Derive consolidated client state from all structured signals.
        
        Args:
            client_id: Client UUID
            db: Database session
            respect_human_values: If True, only suggests updates for fields that are None
                                  or were last updated by AI (not manually)
            only_active_attendances: If True, only include signals from ACTIVE attendances
            max_cycles: If set, only include signals from the most recent N attendances
            use_cluster_logic: If True, groups signals by Attendance to avoid mixing contexts
            
        Returns:
            Dictionary with:
            - suggestions: List of ClientStateSuggestion
            - signals_count: Number of signals processed
            - traceability: Map of field -> source attendance ID
            - field_sources: Map of field -> source type (HUMAN, AI, or None)
        """
        # Get client
        from app.clients.repository import ClientRepository
        client_repo = ClientRepository(db)
        client = client_repo.get_by_id(client_id)
        
        if not client:
            return {
                "suggestions": [],
                "signals_count": 0,
                "traceability": {},
                "field_sources": {},
            }
        
        # Get signals with filtering options
        signals = ClientStateDerivationService.get_all_signals_for_client(
            client_id=client_id,
            db=db,
            only_active_attendances=only_active_attendances,
            max_cycles=max_cycles,
            exclude_if_won=True,  # Exclude old signals if client won
        )
        
        # Derive suggestions with cluster logic
        all_suggestions = ClientStateDerivationService.derive_state_suggestions(
            client=client,
            signals=signals,
            use_cluster_logic=use_cluster_logic,
        )
        
        # Determine field sources and filter suggestions
        field_sources = {}
        filtered_suggestions = []
        
        for suggestion in all_suggestions:
            field_name = suggestion.field_name
            current_value = getattr(client, field_name, None)
            
            # Determine field source
            if current_value is None:
                field_sources[field_name] = None
            elif ClientStateDerivationService._is_field_manually_set(client, field_name, db):
                field_sources[field_name] = "HUMAN"
            else:
                field_sources[field_name] = "AI"
            
            # Filter based on respect_human_values
            if respect_human_values:
                # Only suggest if:
                # - Field is None (not set yet), OR
                # - Field was set by AI (can be updated by newer AI signal)
                if current_value is None or field_sources[field_name] == "AI":
                    filtered_suggestions.append(suggestion)
            else:
                filtered_suggestions.append(suggestion)
        
        suggestions = filtered_suggestions
        
        # Build traceability map
        traceability = {}
        for suggestion in suggestions:
            traceability[suggestion.field_name] = {
                "attendance_id": str(suggestion.source_attendance_id),
                "ai_summary_id": str(suggestion.source_ai_summary_id),
                "confidence": suggestion.confidence,
                "detected_at": suggestion.detected_at.isoformat(),
                "reason": suggestion.reason,
            }
        
        return {
            "suggestions": suggestions,
            "signals_count": len(signals),
            "traceability": traceability,
            "field_sources": field_sources,
        }

