"""Pydantic schemas for property validation and serialization."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.properties.models import BusinessType, PropertyStatus, PropertyType


class PropertyBase(BaseModel):
    """Base schema for property data."""

    code: str = Field(..., min_length=1, max_length=50, description="Property code/reference (unique)")
    title: str = Field(..., min_length=1, max_length=255, description="Property title")
    description: str | None = Field(None, description="Property description")

    # Type
    property_type: PropertyType = Field(..., description="Type of property")
    business_type: BusinessType = Field(..., description="Business type (SALE, RENT, BOTH)")

    # Location
    street: str = Field(..., min_length=1, max_length=255, description="Street address")
    number: str = Field(..., min_length=1, max_length=20, description="Address number")
    neighborhood: str = Field(..., min_length=1, max_length=255, description="Neighborhood")
    city: str = Field(..., min_length=1, max_length=255, description="City")
    state: str = Field(..., min_length=2, max_length=2, description="State (2 letters)")
    zip_code: str = Field(..., min_length=1, max_length=10, description="ZIP code")
    latitude: Decimal | None = Field(None, description="Latitude coordinate")
    longitude: Decimal | None = Field(None, description="Longitude coordinate")

    # Characteristics
    area_total: Decimal | None = Field(None, ge=0, description="Total area in m²")
    area_built: Decimal | None = Field(None, ge=0, description="Built area in m²")
    bedrooms: int | None = Field(None, ge=0, description="Number of bedrooms")
    bathrooms: int | None = Field(None, ge=0, description="Number of bathrooms")
    parking_spaces: int | None = Field(None, ge=0, description="Number of parking spaces")
    floor: int | None = Field(None, description="Floor number (for apartments)")
    has_elevator: bool = Field(False, description="Whether property has elevator")
    furnished: bool = Field(False, description="Whether property is furnished")

    # Financial
    price: Decimal | None = Field(None, ge=0, description="Sale price")
    rent_price: Decimal | None = Field(None, ge=0, description="Rent price")
    condo_fee: Decimal | None = Field(None, ge=0, description="Condominium fee")
    iptu: Decimal | None = Field(None, ge=0, description="IPTU (property tax)")

    # Commercial
    status: PropertyStatus = Field(
        PropertyStatus.DRAFT,
        description="Property status (defaults to DRAFT)",
    )
    assigned_agent_id: uuid.UUID | None = Field(
        None,
        description="UUID of assigned real estate agent (User with 'corretor' role)",
    )

    # Owner
    owner_name: str | None = Field(None, max_length=255, description="Owner name")
    owner_contact: str | None = Field(None, max_length=255, description="Owner contact information")

    # AI / Matching
    visibility_score: int | None = Field(
        None,
        ge=0,
        le=100,
        description="Visibility score for matching (0-100, calculated automatically)",
    )
    ideal_client_profile: str | None = Field(None, description="Ideal client profile description")

    # Media
    main_image_url: str | None = Field(None, max_length=500, description="Main image URL")

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        """Validate state is uppercase."""
        return v.upper()


class PropertyCreate(PropertyBase):
    """
    Schema for creating a new property.

    Required fields: code, title, property_type, business_type, street, number,
    neighborhood, city, state, zip_code.
    All other fields are optional.
    """

    pass


class PropertyUpdate(BaseModel):
    """
    Schema for updating property information.

    All fields are optional to allow partial updates.
    """

    code: str | None = Field(None, min_length=1, max_length=50)
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None

    # Type
    property_type: PropertyType | None = None
    business_type: BusinessType | None = None

    # Location
    street: str | None = Field(None, min_length=1, max_length=255)
    number: str | None = Field(None, min_length=1, max_length=20)
    neighborhood: str | None = Field(None, min_length=1, max_length=255)
    city: str | None = Field(None, min_length=1, max_length=255)
    state: str | None = Field(None, min_length=2, max_length=2)
    zip_code: str | None = Field(None, min_length=1, max_length=10)
    latitude: Decimal | None = None
    longitude: Decimal | None = None

    # Characteristics
    area_total: Decimal | None = Field(None, ge=0)
    area_built: Decimal | None = Field(None, ge=0)
    bedrooms: int | None = Field(None, ge=0)
    bathrooms: int | None = Field(None, ge=0)
    parking_spaces: int | None = Field(None, ge=0)
    floor: int | None = None
    has_elevator: bool | None = None
    furnished: bool | None = None

    # Financial
    price: Decimal | None = Field(None, ge=0)
    rent_price: Decimal | None = Field(None, ge=0)
    condo_fee: Decimal | None = Field(None, ge=0)
    iptu: Decimal | None = Field(None, ge=0)

    # Commercial
    status: PropertyStatus | None = None
    assigned_agent_id: uuid.UUID | None = None

    # Owner
    owner_name: str | None = Field(None, max_length=255)
    owner_contact: str | None = Field(None, max_length=255)

    # AI / Matching
    visibility_score: int | None = Field(None, ge=0, le=100)
    ideal_client_profile: str | None = None

    # Media
    main_image_url: str | None = Field(None, max_length=500)

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str | None) -> str | None:
        """Validate state is uppercase."""
        if v is not None:
            return v.upper()
        return v


class PropertyResponse(PropertyBase):
    """
    Schema for property response.

    Includes all base fields plus id and timestamps.
    """

    id: uuid.UUID
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True

