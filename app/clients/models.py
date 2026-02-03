"""Client model for lead management."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeadSource(str, enum.Enum):
    """Enum for client lead sources."""

    WHATSAPP = "WHATSAPP"
    SITE = "SITE"
    PHONE = "PHONE"


class Client(Base):
    """
    Client model representing leads/clients.

    Attributes:
        id: Unique identifier (UUID)
        name: Client full name
        phone: Client phone number
        email: Client email address
        lead_source: Source of the lead (WHATSAPP, SITE, PHONE)
        created_at: Timestamp when the client was created
        updated_at: Timestamp when the client was last updated
    """

    __tablename__ = "clients"

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
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    lead_source: Mapped[LeadSource] = mapped_column(
        Enum(LeadSource, native_enum=False, length=20),
        nullable=False,
        index=True,
    )
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

    def __repr__(self) -> str:
        """String representation of the Client."""
        return f"<Client(id={self.id}, name={self.name}, email={self.email})>"

