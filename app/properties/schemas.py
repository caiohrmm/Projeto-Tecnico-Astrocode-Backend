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

    # Location (all optional)
    street: str | None = Field(None, max_length=255, description="Street address")
    number: str | None = Field(None, max_length=20, description="Address number")
    neighborhood: str | None = Field(None, max_length=255, description="Neighborhood")
    city: str | None = Field(None, max_length=255, description="City")
    state: str | None = Field(None, max_length=2, description="State (2 letters)")
    zip_code: str | None = Field(None, max_length=10, description="ZIP code")
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
    def validate_state(cls, v: str | None) -> str | None:
        """Validate state is uppercase."""
        if v is not None:
            return v.upper()
        return v
    
    @field_validator("assigned_agent_id", mode="before")
    @classmethod
    def validate_assigned_agent_id(cls, v) -> uuid.UUID | None:
        """Convert empty strings and invalid values to None."""
        if v is None:
            return None
        if isinstance(v, str):
            # Convert empty string or "null" string to None
            if v.strip() == "" or v.strip().lower() == "null":
                return None
            # Try to parse as UUID
            try:
                return uuid.UUID(v)
            except (ValueError, AttributeError):
                return None
        # If it's already a UUID, return as is
        if isinstance(v, uuid.UUID):
            return v
        return None


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

    code: str | None = Field(None, min_length=1, max_length=50, description="Código do imóvel (único)")
    title: str | None = Field(None, min_length=1, max_length=255, description="Título")
    description: str | None = Field(None, description="Descrição")

    # Type
    property_type: PropertyType | None = Field(None, description="Tipo de imóvel")
    business_type: BusinessType | None = Field(None, description="Tipo de negócio (SALE, RENT, BOTH)")

    # Location
    street: str | None = Field(None, min_length=1, max_length=255, description="Rua")
    number: str | None = Field(None, min_length=1, max_length=20, description="Número")
    neighborhood: str | None = Field(None, min_length=1, max_length=255, description="Bairro")
    city: str | None = Field(None, min_length=1, max_length=255, description="Cidade")
    state: str | None = Field(None, min_length=2, max_length=2, description="Estado (2 letras)")
    zip_code: str | None = Field(None, min_length=1, max_length=10, description="CEP")
    latitude: Decimal | None = Field(None, description="Latitude")
    longitude: Decimal | None = Field(None, description="Longitude")

    # Characteristics
    area_total: Decimal | None = Field(None, ge=0, description="Área total (m²)")
    area_built: Decimal | None = Field(None, ge=0, description="Área construída (m²)")
    bedrooms: int | None = Field(None, ge=0, description="Quartos")
    bathrooms: int | None = Field(None, ge=0, description="Banheiros")
    parking_spaces: int | None = Field(None, ge=0, description="Vagas")
    floor: int | None = Field(None, description="Andar (apartamentos)")
    has_elevator: bool | None = Field(None, description="Possui elevador")
    furnished: bool | None = Field(None, description="Mobiliado")

    # Financial
    price: Decimal | None = Field(None, ge=0, description="Preço de venda")
    rent_price: Decimal | None = Field(None, ge=0, description="Preço de aluguel")
    condo_fee: Decimal | None = Field(None, ge=0, description="Condomínio")
    iptu: Decimal | None = Field(None, ge=0, description="IPTU")

    # Commercial
    status: PropertyStatus | None = Field(None, description="Status (DRAFT, PUBLISHED, SOLD, etc.)")
    assigned_agent_id: uuid.UUID | None = Field(None, description="ID do agente (deve ser corretor)")

    # Owner
    owner_name: str | None = Field(None, max_length=255, description="Nome do proprietário")
    owner_contact: str | None = Field(None, max_length=255, description="Contato do proprietário")

    # AI / Matching
    visibility_score: int | None = Field(None, ge=0, le=100, description="Score de visibilidade (0–100)")
    ideal_client_profile: str | None = Field(None, description="Perfil ideal do cliente")

    # Media
    main_image_url: str | None = Field(None, max_length=500, description="URL da imagem principal")

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str | None) -> str | None:
        """Validate state is uppercase."""
        if v is not None:
            return v.upper()
        return v
    
    @field_validator("assigned_agent_id", mode="before")
    @classmethod
    def validate_assigned_agent_id(cls, v) -> uuid.UUID | None:
        """Convert empty strings and invalid values to None."""
        if v is None:
            return None
        if isinstance(v, str):
            # Convert empty string or "null" string to None
            if v.strip() == "" or v.strip().lower() == "null":
                return None
            # Try to parse as UUID
            try:
                return uuid.UUID(v)
            except (ValueError, AttributeError):
                return None
        # If it's already a UUID, return as is
        if isinstance(v, uuid.UUID):
            return v
        return None


class PropertyResponse(PropertyBase):
    """
    Schema for property response.

    Includes all base fields plus id and timestamps.
    """

    id: uuid.UUID = Field(..., description="UUID do imóvel")
    published_at: datetime | None = Field(None, description="Data de publicação (quando status = PUBLISHED)")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: datetime = Field(..., description="Data da última atualização")

    class Config:
        """Pydantic config."""

        from_attributes = True


# Google Places/Geocoding schemas
class AddressComponents(BaseModel):
    """Address component from Google Geocoding API."""

    long_name: str
    short_name: str
    types: list[str]


class GeocodeResult(BaseModel):
    """Result from Google Geocoding API."""

    formatted_address: str
    address_components: list[AddressComponents]
    geometry: dict
    place_id: str


class GeocodeResponse(BaseModel):
    """Response from Google Geocoding API."""

    results: list[GeocodeResult]
    status: str


class AddressData(BaseModel):
    """Endereço parseado retornado pelo geocode (Google)."""

    street: str | None = Field(None, description="Rua")
    number: str | None = Field(None, description="Número")
    neighborhood: str | None = Field(None, description="Bairro")
    city: str | None = Field(None, description="Cidade")
    state: str | None = Field(None, description="Estado (sigla)")
    zip_code: str | None = Field(None, description="CEP")
    latitude: str | None = Field(None, description="Latitude")
    longitude: str | None = Field(None, description="Longitude")
