"""Chat service that orchestrates Gemini API calls with database context."""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.ai.gemini_service import GeminiService
from app.ai.prompts import SYSTEM_PROMPT, build_context_prompt
from app.clients.repository import ClientRepository
from app.properties.repository import PropertyRepository
from app.attendances.repository import AttendanceRepository

logger = logging.getLogger(__name__)

# Horário de Brasília (UTC-3), offset fixo para funcionar em Windows sem tzdata
BRASILIA_TZ = timezone(timedelta(hours=-3))
MONTHS_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _format_datetime_brasilia(dt: datetime | None) -> str | None:
    """Format datetime in Brasília timezone (UTC-3) for display in chat context (e.g. '19 de fevereiro de 2026, às 15:55 (horário de Brasília)')."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(BRASILIA_TZ)
    return (
        f"{local.day} de {MONTHS_PT[local.month - 1]} de {local.year}, "
        f"às {local.hour:02d}:{local.minute:02d} (horário de Brasília)"
    )


class ChatService:
    """Service for handling AI chat requests with database context."""

    def __init__(self, db: Session) -> None:
        """
        Initialize chat service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.gemini_service = GeminiService()
        self.client_repo = ClientRepository(db)
        self.property_repo = PropertyRepository(db)
        self.attendance_repo = AttendanceRepository(db)

    def _build_attendance_context(self, attendance) -> dict[str, Any]:
        """
        Build rich attendance context: AI summary, linked property, visits, sales, losses.
        So the AI assistant has full picture when user asks for "resumo completo" or context.
        """
        from app.ai.repository import AISummaryRepository
        from app.visits.repository import VisitRepository
        from app.sales.repository import SaleRepository
        from app.losses.repository import LossRepository

        data: dict[str, Any] = {
            "created_at": _format_datetime_brasilia(attendance.created_at),
            "updated_at": _format_datetime_brasilia(attendance.updated_at),
            "status": attendance.status.value if attendance.status else None,
            "objective": attendance.objective,
            "raw_content": attendance.raw_content,
            "ai_summary": None,
            "linked_property": None,
            "visits": [],
            "sales": [],
            "losses": [],
            "property_purchased": None,
            "property_lost": None,
        }

        # AI summary for this attendance
        ai_repo = AISummaryRepository(self.db)
        ai_summary = ai_repo.get_by_attendance_id(attendance.id)
        if ai_summary:
            data["ai_summary"] = {
                "summary_text": ai_summary.summary_text,
                "detected_intent": ai_summary.detected_intent.value if ai_summary.detected_intent else None,
                "urgency_level_detected": ai_summary.urgency_level_detected,
                "lead_score_suggested": ai_summary.lead_score_suggested,
                "sentiment": ai_summary.sentiment.value if ai_summary.sentiment else None,
            }
            if ai_summary.key_points and isinstance(ai_summary.key_points, dict):
                data["property_purchased"] = ai_summary.key_points.get("property_purchased")
                data["property_lost"] = ai_summary.key_points.get("property_lost")

        # Linked property (imóvel vinculado ao atendimento)
        if attendance.property_id:
            prop = self.property_repo.get_by_id(attendance.property_id)
            if prop:
                data["linked_property"] = {
                    "code": prop.code,
                    "title": prop.title,
                    "property_type": prop.property_type.value if prop.property_type else None,
                    "status": prop.status.value if prop.status else None,
                    "city": prop.city,
                    "price": float(prop.price) if prop.price else None,
                    "rent_price": float(prop.rent_price) if prop.rent_price else None,
                }

        # Visits for this attendance
        visit_repo = VisitRepository(self.db)
        visits = visit_repo.get_all(attendance_id=attendance.id, limit=20)
        for v in visits:
            prop_desc = None
            if v.property_id:
                p = self.property_repo.get_by_id(v.property_id)
                prop_desc = f"{p.code} - {p.title}" if p else str(v.property_id)
            data["visits"].append({
                "scheduled_at": _format_datetime_brasilia(v.scheduled_at),
                "status": v.status.value if v.status else None,
                "property": prop_desc,
            })

        # Sales for this client (so we know if the linked property was sold)
        sale_repo = SaleRepository(self.db)
        sales = sale_repo.get_all(client_id=attendance.client_id, limit=10)
        for s in sales:
            prop_desc = None
            if s.property_id:
                p = self.property_repo.get_by_id(s.property_id)
                prop_desc = f"{p.code} - {p.title}" if p else str(s.property_id)
            is_linked = s.property_id == attendance.property_id if attendance.property_id else False
            data["sales"].append({
                "property": prop_desc,
                "sale_type": s.sale_type.value if s.sale_type else None,
                "sale_value": float(s.sale_value) if s.sale_value else None,
                "created_at": _format_datetime_brasilia(s.created_at),
                "is_linked_to_this_attendance": is_linked,
            })

        # Losses for this client
        loss_repo = LossRepository(self.db)
        losses = loss_repo.get_all(client_id=attendance.client_id, limit=5)
        for lo in losses:
            prop_desc = None
            if lo.property_id:
                p = self.property_repo.get_by_id(lo.property_id)
                prop_desc = f"{p.code} - {p.title}" if p else str(lo.property_id)
            data["losses"].append({
                "reason": lo.loss_reason.value if lo.loss_reason else None,
                "detailed_reason": lo.detailed_reason,
                "property": prop_desc,
                "lost_at": _format_datetime_brasilia(lo.lost_at),
            })

        return data

    def load_context(
        self,
        client_id: uuid.UUID | None = None,
        property_id: uuid.UUID | None = None,
        attendance_id: uuid.UUID | None = None,
        include_dashboard: bool = False,
    ) -> dict[str, Any]:
        """
        Load context data from database based on provided IDs.
        
        When attendance_id is provided, context is enriched with: AI summary,
        linked property, visits, sales and losses for the client, so the
        assistant can give a complete, up-to-date summary of the attendance.
        
        Args:
            client_id: Optional client ID
            property_id: Optional property ID
            attendance_id: Optional attendance ID
            include_dashboard: If True, load dashboard metrics for gestor interpretation
        
        Returns:
            Dictionary with loaded context data
        
        Raises:
            ValueError: If any ID is invalid or not found
        """
        context = {
            "client_data": None,
            "property_data": None,
            "attendance_data": None,
            "dashboard_data": None,
        }

        # Load client data
        if client_id:
            client = self.client_repo.get_by_id(client_id)
            if not client:
                raise ValueError(f"Client with ID {client_id} not found")
            
            context["client_data"] = {
                "name": client.name,
                "email": client.email,
                "phone": client.phone,
                "current_status": client.current_status.value if client.current_status else None,
                "current_lead_score": client.current_lead_score,
                "current_interest_type": client.current_interest_type.value if client.current_interest_type else None,
                "current_budget_min": float(client.current_budget_min) if client.current_budget_min else None,
                "current_budget_max": float(client.current_budget_max) if client.current_budget_max else None,
                "current_city_interest": client.current_city_interest,
                "current_urgency_level": client.current_urgency_level.value if client.current_urgency_level else None,
            }

        # Load property data
        if property_id:
            property_obj = self.property_repo.get_by_id(property_id)
            if not property_obj:
                raise ValueError(f"Property with ID {property_id} not found")
            
            context["property_data"] = {
                "code": property_obj.code,
                "title": property_obj.title,
                "property_type": property_obj.property_type.value if property_obj.property_type else None,
                "business_type": property_obj.business_type.value if property_obj.business_type else None,
                "status": property_obj.status.value if property_obj.status else None,
                "street": property_obj.street,
                "number": property_obj.number,
                "neighborhood": property_obj.neighborhood,
                "city": property_obj.city,
                "state": property_obj.state,
                "zip_code": property_obj.zip_code,
                "price": float(property_obj.price) if property_obj.price else None,
                "rent_price": float(property_obj.rent_price) if property_obj.rent_price else None,
                "bedrooms": property_obj.bedrooms,
                "bathrooms": property_obj.bathrooms,
                "area_total": float(property_obj.area_total) if property_obj.area_total else None,
                "area_built": float(property_obj.area_built) if property_obj.area_built else None,
            }

        # Load attendance data (rich context: AI summary, linked property, visits, sales, losses)
        if attendance_id:
            attendance = self.attendance_repo.get_by_id(attendance_id)
            if not attendance:
                raise ValueError(f"Attendance with ID {attendance_id} not found")
            
            context["attendance_data"] = self._build_attendance_context(attendance)

            # When in attendance context, also load client so the assistant has full picture
            if not context["client_data"] and attendance.client_id:
                client = self.client_repo.get_by_id(attendance.client_id)
                if client:
                    context["client_data"] = {
                        "name": client.name,
                        "email": client.email,
                        "phone": client.phone,
                        "current_status": client.current_status.value if client.current_status else None,
                        "current_lead_score": client.current_lead_score,
                        "current_interest_type": client.current_interest_type.value if client.current_interest_type else None,
                        "current_budget_min": float(client.current_budget_min) if client.current_budget_min else None,
                        "current_budget_max": float(client.current_budget_max) if client.current_budget_max else None,
                        "current_city_interest": client.current_city_interest,
                        "current_urgency_level": client.current_urgency_level.value if client.current_urgency_level else None,
                    }

        # Load dashboard metrics when requested (e.g. from dashboard page or when user asks for dashboard summary)
        if include_dashboard:
            from app.dashboard.service import get_dashboard_context_for_chat
            try:
                context["dashboard_data"] = get_dashboard_context_for_chat(self.db)
            except Exception as e:
                logger.exception("Could not load dashboard context: %s", e)
                context["dashboard_data"] = None

        return context

    def get_response(
        self,
        message: str,
        context_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Get AI response for a message with optional context.
        
        Args:
            message: User's message/question
            context_data: Optional context data from database
        
        Returns:
            Dictionary with 'answer' and 'error' keys
        """
        # Build context string from loaded data
        context_string = None
        if context_data:
            context_string = build_context_prompt(
                client_data=context_data.get("client_data"),
                property_data=context_data.get("property_data"),
                attendance_data=context_data.get("attendance_data"),
                dashboard_data=context_data.get("dashboard_data"),
            )

        # Call Gemini API
        response = self.gemini_service.chat(
            message=message,
            system_prompt=SYSTEM_PROMPT,
            context=context_string,
        )

        return response

