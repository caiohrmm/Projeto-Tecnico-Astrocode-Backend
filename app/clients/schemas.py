"""Pydantic schemas for client validation and serialization."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.clients.models import LeadSource


class ClientBase(BaseModel):
    """Base schema with common client fields."""

    name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=1, max_length=20)
    email: EmailStr
    lead_source: LeadSource


class ClientCreate(ClientBase):
    """
    Schema for creating a new client.

    Attributes:
        name: Client full name
        phone: Client phone number
        email: Client email address
        lead_source: Source of the lead (WHATSAPP, SITE, PHONE)
    """

    pass


class ClientUpdate(BaseModel):
    """
    Schema for updating client information.

    All fields are optional to allow partial updates.
    """

    name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = Field(None, min_length=1, max_length=20)
    email: EmailStr | None = None
    lead_source: LeadSource | None = None


class ClientResponse(ClientBase):
    """
    Schema for client response (serialization).

    Includes all client information with timestamps.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ClientInDB(ClientResponse):
    """
    Schema for client stored in database.

    Same as ClientResponse, kept for consistency with other domains.
    """

    pass

