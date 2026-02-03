"""Pydantic schemas for client validation and serialization."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator

from app.clients.models import (
    ClientStatus,
    InterestType,
    LeadSource,
    PropertyType,
    UrgencyLevel,
)


class ClientBase(BaseModel):
    """Base schema with common client fields."""

    name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=1, max_length=20)
    email: EmailStr
    lead_source: LeadSource


class ClientCreate(ClientBase):
    """
    Schema for creating a new client.

    Only required fields: name, phone, email, lead_source.
    All other fields are optional and can be set later.
    """

    # Funnel Status & Scoring (optional)
    current_status: ClientStatus | None = Field(
        None,
        description="Current stage in sales funnel (defaults to NEW_LEAD)",
    )
    current_lead_score: int | None = Field(
        None,
        ge=0,
        le=100,
        description="Lead score from 0 to 100 for prioritization",
    )
    current_urgency_level: UrgencyLevel | None = Field(
        None,
        description="Urgency level (LOW, MEDIUM, HIGH, IMMEDIATE)",
    )

    # Commercial Assignment (optional)
    assigned_agent_id: uuid.UUID | None = Field(
        None,
        description="UUID of assigned real estate agent (User)",
    )

    # Client Interest (optional)
    current_interest_type: InterestType | None = Field(
        None,
        description="Type of interest (BUY, RENT, SELL, INVEST)",
    )
    current_property_type: PropertyType | None = Field(
        None,
        description="Property type of interest",
    )
    current_budget_min: Decimal | None = Field(
        None,
        ge=0,
        description="Minimum budget",
    )
    current_budget_max: Decimal | None = Field(
        None,
        ge=0,
        description="Maximum budget",
    )
    current_city_interest: str | None = Field(
        None,
        max_length=255,
        description="City where client wants property",
    )

    # Relationship Management (optional)
    first_contact_at: datetime | None = Field(
        None,
        description="Date of first contact",
    )
    last_contact_at: datetime | None = Field(
        None,
        description="Date of last contact",
    )
    next_follow_up_at: datetime | None = Field(
        None,
        description="Scheduled next follow-up date",
    )
    summary_notes: str | None = Field(
        None,
        description="Summary notes about the client",
    )

    @field_validator("current_budget_max")
    @classmethod
    def validate_budget_range(cls, v: Decimal | None, info) -> Decimal | None:
        """Validate that max budget is greater than or equal to min budget."""
        if v is not None and "current_budget_min" in info.data:
            min_budget = info.data.get("current_budget_min")
            if min_budget is not None and v < min_budget:
                raise ValueError("current_budget_max must be >= current_budget_min")
        return v


class ClientUpdate(BaseModel):
    """
    Schema for updating client information.

    All fields are optional to allow partial updates.
    """

    name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = Field(None, min_length=1, max_length=20)
    email: EmailStr | None = None
    lead_source: LeadSource | None = None

    # Funnel Status & Scoring
    current_status: ClientStatus | None = None
    current_lead_score: int | None = Field(None, ge=0, le=100)
    current_urgency_level: UrgencyLevel | None = None

    # Commercial Assignment
    assigned_agent_id: uuid.UUID | None = None

    # Client Interest
    current_interest_type: InterestType | None = None
    current_property_type: PropertyType | None = None
    current_budget_min: Decimal | None = Field(None, ge=0)
    current_budget_max: Decimal | None = Field(None, ge=0)
    current_city_interest: str | None = Field(None, max_length=255)

    # Relationship Management
    first_contact_at: datetime | None = None
    last_contact_at: datetime | None = None
    next_follow_up_at: datetime | None = None
    summary_notes: str | None = None

    @field_validator("current_budget_max")
    @classmethod
    def validate_budget_range(cls, v: Decimal | None, info) -> Decimal | None:
        """Validate that max budget is greater than or equal to min budget."""
        if v is not None and "current_budget_min" in info.data:
            min_budget = info.data.get("current_budget_min")
            if min_budget is not None and v < min_budget:
                raise ValueError("current_budget_max must be >= current_budget_min")
        return v


class ClientResponse(ClientBase):
    """
    Schema for client response (serialization).

    Includes all client information with timestamps and optional fields.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID

    # Funnel Status & Scoring
    current_status: ClientStatus | None = None
    current_lead_score: int | None = None
    current_urgency_level: UrgencyLevel | None = None

    # Commercial Assignment
    assigned_agent_id: uuid.UUID | None = None

    # Client Interest
    current_interest_type: InterestType | None = None
    current_property_type: PropertyType | None = None
    current_budget_min: Decimal | None = None
    current_budget_max: Decimal | None = None
    current_city_interest: str | None = None

    # Relationship Management
    first_contact_at: datetime | None = None
    last_contact_at: datetime | None = None
    next_follow_up_at: datetime | None = None
    summary_notes: str | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime


class ClientInDB(ClientResponse):
    """
    Schema for client stored in database.

    Same as ClientResponse, kept for consistency with other domains.
    """

    pass


