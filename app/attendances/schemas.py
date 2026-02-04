"""Pydantic schemas for attendance validation and serialization."""

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
    channel: AttendanceChannel = Field(..., description="Communication channel")
    started_at: datetime = Field(..., description="When the attendance started")
    ended_at: datetime | None = Field(None, description="When the attendance ended")
    raw_content: str = Field(..., min_length=1, description="Raw content of the attendance")
    ai_summary: str | None = Field(None, description="AI-generated summary")
    ai_next_steps: str | None = Field(None, description="AI-generated next steps")
    status: AttendanceStatus = Field(
        AttendanceStatus.IN_PROGRESS,
        description="Attendance status (defaults to IN_PROGRESS)",
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

    Required fields: client_id, agent_id, channel, started_at, raw_content.
    Duration is calculated automatically when ended_at is provided.
    """

    pass


class AttendanceUpdate(BaseModel):
    """
    Schema for updating attendance information.

    All fields are optional to allow partial updates.
    Duration is recalculated automatically if ended_at is updated.
    """

    client_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    property_id: uuid.UUID | None = None
    channel: AttendanceChannel | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    raw_content: str | None = Field(None, min_length=1)
    ai_summary: str | None = None
    ai_next_steps: str | None = None
    status: AttendanceStatus | None = None
    updated_client_status: ClientStatusUpdate | None = None
    scheduled_visit_at: datetime | None = None


class AttendanceResponse(AttendanceBase):
    """
    Schema for attendance response.

    Includes all base fields plus id, duration, and timestamps.
    Duration is calculated automatically.
    """

    id: uuid.UUID
    duration: int | None = Field(
        None,
        description="Duration in seconds (calculated automatically when ended_at is set)",
    )
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def parse_updated_client_status(cls, data: Any) -> Any:
        """Parse updated_client_status from JSON string if needed."""
        if isinstance(data, dict) and "updated_client_status" in data:
            updated_status = data["updated_client_status"]
            if isinstance(updated_status, str):
                try:
                    data["updated_client_status"] = json.loads(updated_status)
                except (json.JSONDecodeError, TypeError):
                    data["updated_client_status"] = None
        return data

    class Config:
        """Pydantic config."""

        from_attributes = True

