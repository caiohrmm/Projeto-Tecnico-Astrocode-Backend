"""Attendance model for client service tracking."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.clients.models import Client
    from app.properties.models import Property
    from app.users.models import User


class AttendanceChannel(str, enum.Enum):
    """Enum for attendance channel."""

    WHATSAPP = "WHATSAPP"
    SITE = "SITE"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    IN_PERSON = "IN_PERSON"


class AttendanceStatus(str, enum.Enum):
    """Enum for attendance status."""

    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


class Attendance(Base):
    """
    Attendance model representing client service interactions.

    Attributes:
        id: Unique identifier (UUID)
        client_id: Foreign key to Client
        agent_id: Foreign key to User (real estate agent)
        property_id: Foreign key to Property (nullable)
        channel: Communication channel (WHATSAPP, SITE, PHONE, EMAIL, IN_PERSON)
        started_at: When the attendance started
        ended_at: When the attendance ended (nullable)
        duration: Duration in seconds (calculated automatically)
        raw_content: Raw content of the attendance conversation
        ai_summary: AI-generated summary of the attendance
        ai_next_steps: AI-generated next steps for the client
        status: Attendance status (IN_PROGRESS, COMPLETED, CANCELLED, PAUSED)
        updated_client_status: JSON field to update client status fields
        scheduled_visit_at: Scheduled visit date/time (nullable)
        created_at: Timestamp when attendance was created
        updated_at: Timestamp when attendance was last updated
        
        # Relationships
        client: Relationship to Client
        agent: Relationship to User (agent)
        property: Relationship to Property
    """

    __tablename__ = "attendances"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Relationships
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    property_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Attendance details
    channel: Mapped[AttendanceChannel] = mapped_column(
        Enum(AttendanceChannel, native_enum=False, length=20),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Duration in seconds, calculated automatically when ended_at is set",
    )

    # Content
    raw_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    ai_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    ai_next_steps: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Status and actions
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, native_enum=False, length=20),
        default=AttendanceStatus.IN_PROGRESS,
        nullable=False,
        index=True,
    )

    # Client status updates (stored as JSON string, will be parsed in schemas)
    updated_client_status: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON string with client status updates: current_status, current_interest_type, current_property_type",
    )

    # Scheduled visit
    scheduled_visit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
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
    client: Mapped["Client"] = relationship(
        "Client",
        foreign_keys=[client_id],
        lazy="selectin",
    )
    agent: Mapped["User"] = relationship(
        "User",
        foreign_keys=[agent_id],
        lazy="selectin",
    )
    property: Mapped["Property | None"] = relationship(
        "Property",
        foreign_keys=[property_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation of the Attendance."""
        return f"<Attendance(id={self.id}, client_id={self.client_id}, channel={self.channel}, status={self.status})>"

