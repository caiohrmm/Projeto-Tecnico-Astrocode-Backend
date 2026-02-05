"""Chat service that orchestrates Gemini API calls with database context."""

import uuid
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.ai.gemini_service import GeminiService
from app.ai.prompts import SYSTEM_PROMPT, build_context_prompt
from app.clients.repository import ClientRepository
from app.properties.repository import PropertyRepository
from app.attendances.repository import AttendanceRepository

logger = logging.getLogger(__name__)


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

    def load_context(
        self,
        client_id: uuid.UUID | None = None,
        property_id: uuid.UUID | None = None,
        attendance_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Load context data from database based on provided IDs.
        
        Args:
            client_id: Optional client ID
            property_id: Optional property ID
            attendance_id: Optional attendance ID
        
        Returns:
            Dictionary with loaded context data
        
        Raises:
            ValueError: If any ID is invalid or not found
        """
        context = {
            "client_data": None,
            "property_data": None,
            "attendance_data": None,
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

        # Load attendance data
        if attendance_id:
            attendance = self.attendance_repo.get_by_id(attendance_id)
            if not attendance:
                raise ValueError(f"Attendance with ID {attendance_id} not found")
            
            context["attendance_data"] = {
                "started_at": attendance.started_at.isoformat() if attendance.started_at else None,
                "channel": attendance.channel.value if attendance.channel else None,
                "status": attendance.status.value if attendance.status else None,
                "raw_content": attendance.raw_content,
            }

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
            )

        # Call Gemini API
        response = self.gemini_service.chat(
            message=message,
            system_prompt=SYSTEM_PROMPT,
            context=context_string,
        )

        return response

