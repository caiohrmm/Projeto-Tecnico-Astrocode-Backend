"""Pydantic schemas for attendance validation and serialization."""

import enum
import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.attendances.models import AttendanceChannel, AttendanceStatus
from app.clients.models import ClientStatus, InterestType, PropertyType


class ClientStatusUpdate(BaseModel):
    """Schema for updating client status from attendance."""

    current_status: ClientStatus | None = None
    current_interest_type: InterestType | None = None
    current_property_type: PropertyType | None = None


class AttendanceBase(BaseModel):
    """Base schema for attendance data."""

    client_id: uuid.UUID = Field(..., description="Client ID (required)")
    agent_id: uuid.UUID = Field(..., description="Agent ID (required, must be corretor)")
    property_id: uuid.UUID | None = Field(None, description="Property ID (nullable)")
    objective: str | None = Field(
        None,
        description="Clear objective of this interaction cycle (e.g., 'Purchase residential property in City X'). Can be auto-detected from content if not provided.",
    )
    channel: AttendanceChannel = Field(..., description="Communication channel")
    started_at: datetime = Field(..., description="When the attendance cycle started")
    ended_at: datetime | None = Field(None, description="When the attendance cycle ended")
    raw_content: str = Field(
        ...,
        min_length=1,
        max_length=100000,  # 100k chars limit to avoid performance issues
        description="Raw content of conversations (can accumulate over time within the same cycle). Maximum 100,000 characters.",
    )
    ai_summary: str | None = Field(None, description="AI-generated summary")
    ai_next_steps: str | None = Field(None, description="AI-generated next steps")
    status: AttendanceStatus = Field(
        AttendanceStatus.ACTIVE,
        description="Attendance status (defaults to ACTIVE)",
    )
    updated_client_status: ClientStatusUpdate | None = Field(
        None,
        description="Client status updates (current_status, current_interest_type, current_property_type)",
    )
    scheduled_visit_at: datetime | None = Field(
        None,
        description="Scheduled visit date/time (will create a visit if provided)",
    )



class AttendanceCreate(AttendanceBase):
    """
    Schema for creating a new attendance.

    **Cycle Logic:**
    - If the client has an active attendance with the same objective, the new content
      will be accumulated into the existing attendance (conversation continues).
    - If the objective has changed significantly, the previous active attendance will be
      closed (ABANDONED) and a new attendance cycle will be created.
    - If no objective is provided, it will be auto-detected from the raw_content.

    **Required fields:** client_id, agent_id, channel, raw_content.
    
    **Automatic behaviors:**
    - AI summary is generated automatically.
    - Objective is auto-detected if not provided.
    """

    pass


class AttendanceUpdate(BaseModel):
    """
    Schema for updating attendance information.

    **Important Notes:**
    - All fields are optional to allow partial updates.
    - If `status` is changed to COMPLETED, AI summary will be regenerated automatically.
    - If `raw_content` or other AI-relevant fields are updated for a COMPLETED attendance,
      the AI summary will be regenerated.
    - If you update the `objective` field for an ACTIVE attendance, consider whether
      this should trigger a new cycle instead (manual control).

    """

    client_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    property_id: uuid.UUID | None = None
    objective: str | None = None
    channel: AttendanceChannel | None = None
    raw_content: str | None = Field(
        None,
        min_length=1,
        max_length=100000,  # 100k chars limit to avoid performance issues
        description="Raw content of conversations. Maximum 100,000 characters.",
    )
    ai_summary: str | None = None
    ai_next_steps: str | None = None
    status: AttendanceStatus | None = None
    updated_client_status: ClientStatusUpdate | None = None
    scheduled_visit_at: datetime | None = None



class CycleAction(str, enum.Enum):
    """Enum for cycle action taken when creating/updating attendance."""
    NEW_CYCLE_CREATED = "NEW_CYCLE_CREATED"
    CYCLE_UPDATED = "CYCLE_UPDATED"
    PREVIOUS_CYCLE_CLOSED = "PREVIOUS_CYCLE_CLOSED"


class AttendanceResponse(BaseModel):
    """
    Schema for attendance response.

    Includes all base fields plus id and timestamps.
    """

    id: uuid.UUID
    client_id: uuid.UUID = Field(..., description="Client ID (required)")
    agent_id: uuid.UUID = Field(..., description="Agent ID (required, must be corretor)")
    property_id: uuid.UUID | None = Field(None, description="Property ID (nullable)")
    objective: str | None = Field(None, description="Clear objective of this interaction cycle")
    channel: AttendanceChannel = Field(..., description="Communication channel")
    raw_content: str = Field(..., min_length=1, description="Raw content of conversations")
    ai_summary: str | None = Field(None, description="AI-generated summary")
    ai_next_steps: str | None = Field(None, description="AI-generated next steps")
    status: AttendanceStatus = Field(
        AttendanceStatus.ACTIVE,
        description="Attendance status",
    )
    updated_client_status: ClientStatusUpdate | None = Field(
        None,
        description="Client status updates (current_status, current_interest_type, current_property_type)",
    )
    scheduled_visit_at: datetime | None = Field(
        None,
        description="Scheduled visit date/time (will create a visit if provided)",
    )
    created_at: datetime
    updated_at: datetime
    cycle_action: CycleAction | None = Field(
        None,
        description="Action taken: NEW_CYCLE_CREATED, CYCLE_UPDATED, or PREVIOUS_CYCLE_CLOSED. Only present when creating/updating via POST.",
    )
    previous_cycle_id: uuid.UUID | None = Field(
        None,
        description="ID of the previous cycle that was closed (if any). Only present when NEW_CYCLE_CREATED.",
    )

    @model_validator(mode="before")
    @classmethod
    def parse_updated_client_status(cls, data: Any) -> Any:
        """Parse updated_client_status from JSON string if needed."""
        # Handle SQLAlchemy model instance
        if hasattr(data, "__dict__"):
            if hasattr(data, "updated_client_status"):
                updated_status = data.updated_client_status
                if isinstance(updated_status, str) and updated_status.strip():
                    try:
                        parsed = json.loads(updated_status)
                        data.updated_client_status = ClientStatusUpdate(**parsed) if parsed else None
                    except (json.JSONDecodeError, TypeError, ValueError):
                        data.updated_client_status = None
                elif updated_status is None or updated_status == "":
                    data.updated_client_status = None
        # Handle dict
        elif isinstance(data, dict) and "updated_client_status" in data:
            updated_status = data["updated_client_status"]
            if isinstance(updated_status, str) and updated_status.strip():
                try:
                    parsed = json.loads(updated_status)
                    data["updated_client_status"] = ClientStatusUpdate(**parsed) if parsed else None
                except (json.JSONDecodeError, TypeError, ValueError):
                    data["updated_client_status"] = None
            elif updated_status is None or updated_status == "":
                data["updated_client_status"] = None
        return data

    class Config:
        """Pydantic config."""

        from_attributes = True

