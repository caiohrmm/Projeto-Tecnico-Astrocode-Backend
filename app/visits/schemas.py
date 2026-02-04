"""Pydantic schemas for visit validation and serialization."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.visits.models import VisitStatus


class VisitBase(BaseModel):
    """Base schema for visit data."""

    attendance_id: uuid.UUID | None = Field(
        None,
        description="Attendance ID (can be linked to attendance system)",
    )
    property_id: uuid.UUID | None = Field(
        None,
        description="Property ID (nullable - visit can be without property)",
    )
    client_id: uuid.UUID = Field(
        ...,
        description="Client ID (required)",
    )
    broker_id: uuid.UUID = Field(
        ...,
        description="Broker/Agent ID (required)",
    )
    scheduled_at: datetime = Field(
        ...,
        description="Scheduled date and time for the visit",
    )
    status: VisitStatus = Field(
        VisitStatus.SCHEDULED,
        description="Visit status (defaults to SCHEDULED)",
    )
    notes: str | None = Field(
        None,
        description="Optional notes about the visit",
    )


class VisitCreate(VisitBase):
    """
    Schema for creating a new visit.

    Required fields: client_id, broker_id, scheduled_at.
    All other fields are optional.
    """

    pass


class VisitUpdate(BaseModel):
    """
    Schema for updating visit information.

    All fields are optional to allow partial updates.
    """

    attendance_id: uuid.UUID | None = None
    property_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    broker_id: uuid.UUID | None = None
    scheduled_at: datetime | None = None
    status: VisitStatus | None = None
    notes: str | None = None


class VisitResponse(VisitBase):
    """
    Schema for visit response.

    Includes all base fields plus id and timestamps.
    """

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True

