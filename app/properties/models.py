"""Property model for real estate management."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.users.models import User


class PropertyType(str, enum.Enum):
    """Enum for property type."""

    HOUSE = "HOUSE"
    APARTMENT = "APARTMENT"
    LAND = "LAND"
    COMMERCIAL = "COMMERCIAL"
    RURAL = "RURAL"


class BusinessType(str, enum.Enum):
    """Enum for business type (sale/rent)."""

    SALE = "SALE"
    RENT = "RENT"
    BOTH = "BOTH"


class PropertyStatus(str, enum.Enum):
    """Enum for property status."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    SOLD = "SOLD"
    RENTED = "RENTED"
    UNAVAILABLE = "UNAVAILABLE"


class Property(Base):
    """
    Property model representing real estate properties.

    Attributes:
        id: Unique identifier (UUID)
        code: Property code/reference (unique)
        title: Property title
        description: Property description
        
        # Type
        property_type: Type of property (HOUSE, APARTMENT, LAND, COMMERCIAL, RURAL)
        business_type: Business type (SALE, RENT, BOTH)
        
        # Location
        street: Street address
        number: Address number
        neighborhood: Neighborhood
        city: City
        state: State
        zip_code: ZIP code
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        
        # Characteristics
        area_total: Total area in m²
        area_built: Built area in m²
        bedrooms: Number of bedrooms
        bathrooms: Number of bathrooms
        parking_spaces: Number of parking spaces
        floor: Floor number (for apartments)
        has_elevator: Whether property has elevator
        furnished: Whether property is furnished
        
        # Financial
        price: Sale price
        rent_price: Rent price
        condo_fee: Condominium fee
        iptu: IPTU (property tax)
        
        # Commercial
        status: Property status (DRAFT, PUBLISHED, SOLD, RENTED, UNAVAILABLE)
        assigned_agent_id: Foreign key to User (assigned real estate agent)
        
        # Owner
        owner_name: Owner name
        owner_contact: Owner contact information
        
        # AI / Matching
        visibility_score: Visibility score for matching (0-100)
        ideal_client_profile: Ideal client profile description
        
        # Media
        main_image_url: Main image URL
        
        # Timestamps
        created_at: Timestamp when property was created
        updated_at: Timestamp when property was last updated
        published_at: Timestamp when property was published
        
        # Relationships
        assigned_agent: Relationship to User (assigned agent)
    """

    __tablename__ = "properties"

    # Identification
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Type
    property_type: Mapped[PropertyType] = mapped_column(
        Enum(PropertyType, native_enum=False, length=20),
        nullable=False,
        index=True,
    )
    business_type: Mapped[BusinessType] = mapped_column(
        Enum(BusinessType, native_enum=False, length=20),
        nullable=False,
        index=True,
    )

    # Location
    street: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    neighborhood: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    city: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    state: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        index=True,
    )
    zip_code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
    )
    latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 8),
        nullable=True,
    )
    longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(11, 8),
        nullable=True,
    )

    # Characteristics
    area_total: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    area_built: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    bedrooms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    bathrooms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    parking_spaces: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    floor: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    has_elevator: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    furnished: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Financial
    price: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        index=True,
    )
    rent_price: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        index=True,
    )
    condo_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    iptu: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Commercial
    status: Mapped[PropertyStatus] = mapped_column(
        Enum(PropertyStatus, native_enum=False, length=20),
        default=PropertyStatus.DRAFT,
        nullable=False,
        index=True,
    )
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Owner
    owner_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    owner_contact: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # AI / Matching
    visibility_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    ideal_client_profile: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Media
    main_image_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # Relationships
    assigned_agent: Mapped["User"] = relationship(
        "User",
        foreign_keys=[assigned_agent_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation of the Property."""
        return f"<Property(id={self.id}, code={self.code}, title={self.title}, status={self.status})>"

