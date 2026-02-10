"""Client model for lead management."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LeadSource(str, enum.Enum):
    """Enum for client lead sources."""

    WHATSAPP = "WHATSAPP"
    SITE = "SITE"
    PHONE = "PHONE"


class ClientStatus(str, enum.Enum):
    """Enum for client funnel status."""

    NEW_LEAD = "NEW_LEAD"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    VISIT_SCHEDULED = "VISIT_SCHEDULED"
    VISITING = "VISITING"
    PROPOSAL_SENT = "PROPOSAL_SENT"
    NEGOTIATING = "NEGOTIATING"
    WON = "WON"
    LOST = "LOST"
    INACTIVE = "INACTIVE"


class UrgencyLevel(str, enum.Enum):
    """Enum for client urgency level."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    IMMEDIATE = "IMMEDIATE"


class InterestType(str, enum.Enum):
    """Enum for client interest type."""

    BUY = "BUY"
    RENT = "RENT"
    SELL = "SELL"
    INVEST = "INVEST"


class PropertyType(str, enum.Enum):
    """Enum for property type of interest."""

    HOUSE = "HOUSE"
    APARTMENT = "APARTMENT"
    LAND = "LAND"
    COMMERCIAL = "COMMERCIAL"
    RURAL = "RURAL"


class Client(Base):
    """
    Client model representing leads/clients with full funnel tracking.

    Attributes:
        id: Unique identifier (UUID)
        name: Client full name (required)
        phone: Client phone number (required)
        email: Client email address (required)
        lead_source: Source of the lead (WHATSAPP, SITE, PHONE) (required)
        
        # Funnel Status & Scoring
        current_status: Current stage in the sales funnel
        current_lead_score: Lead score from 0 to 100 for prioritization
        current_urgency_level: Urgency level (LOW, MEDIUM, HIGH, IMMEDIATE)
        
        # Commercial Assignment
        assigned_agent_id: Foreign key to User (assigned real estate agent)
        
        # Client Interest
        current_interest_type: Type of interest (BUY, RENT, SELL, INVEST)
        current_property_type: Property type of interest
        current_budget_min: Minimum budget
        current_budget_max: Maximum budget
        current_city_interest: City where client wants property
        
        # Relationship Management
        first_contact_at: Date of first contact
        last_contact_at: Date of last contact
        next_follow_up_at: Scheduled next follow-up date
        summary_notes: Summary notes about the client
        
        # Timestamps
        created_at: Timestamp when the client was created
        updated_at: Timestamp when the client was last updated
        
        # Relationships
        assigned_agent: Relationship to User (assigned agent)
    """

    __tablename__ = "clients"

    # Required fields
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    lead_source: Mapped[LeadSource] = mapped_column(
        Enum(LeadSource, native_enum=False, length=20),
        nullable=False,
        index=True,
    )

    # Funnel Status & Scoring
    current_status: Mapped[ClientStatus | None] = mapped_column(
        Enum(ClientStatus, native_enum=False, length=20),
        nullable=True,
        index=True,
    )
    current_lead_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    current_urgency_level: Mapped[UrgencyLevel | None] = mapped_column(
        Enum(UrgencyLevel, native_enum=False, length=20),
        nullable=True,
        index=True,
    )

    # Commercial Assignment
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Client Interest
    current_interest_type: Mapped[InterestType | None] = mapped_column(
        Enum(InterestType, native_enum=False, length=20),
        nullable=True,
        index=True,
    )
    current_property_type: Mapped[PropertyType | None] = mapped_column(
        Enum(PropertyType, native_enum=False, length=20),
        nullable=True,
        index=True,
    )
    current_budget_min: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    current_budget_max: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    current_city_interest: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Relationship Management
    first_contact_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    last_contact_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    next_follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    summary_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    initial_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="First message from the client (used for AI classification)",
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

    # Relationships
    assigned_agent: Mapped["User"] = relationship(
        "User",
        foreign_keys=[assigned_agent_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation of the Client."""
        return f"<Client(id={self.id}, name={self.name}, email={self.email}, status={self.current_status})>"


