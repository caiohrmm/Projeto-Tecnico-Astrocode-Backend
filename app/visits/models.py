"""Visit model for visit scheduling and tracking."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.clients.models import Client
    from app.properties.models import Property
    from app.users.models import User


class VisitStatus(str, enum.Enum):
    """Enum for visit status."""

    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class Visit(Base):
    """
    Visit model representing scheduled property visits.

    Attributes:
        id: Unique identifier (UUID)
        attendance_id: Attendance ID (can be linked to attendance system)
        property_id: Foreign key to Property (nullable - visit can be without property)
        client_id: Foreign key to Client
        broker_id: Foreign key to User (real estate agent/broker)
        scheduled_at: Scheduled date and time for the visit
        status: Visit status (SCHEDULED, CONFIRMED, IN_PROGRESS, COMPLETED, CANCELLED, NO_SHOW)
        notes: Optional notes about the visit
        created_at: Timestamp when visit was created
        updated_at: Timestamp when visit was last updated
        
        # Relationships
        property: Relationship to Property
        client: Relationship to Client
        broker: Relationship to User (broker)
    """

    __tablename__ = "visits"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Attendance and relationships
    attendance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    property_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Visit details
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    status: Mapped[VisitStatus] = mapped_column(
        Enum(VisitStatus, native_enum=False, length=20),
        default=VisitStatus.SCHEDULED,
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
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

    # Relationships
    property: Mapped["Property | None"] = relationship(
        "Property",
        foreign_keys=[property_id],
        lazy="selectin",
    )
    client: Mapped["Client"] = relationship(
        "Client",
        foreign_keys=[client_id],
        lazy="selectin",
    )
    broker: Mapped["User"] = relationship(
        "User",
        foreign_keys=[broker_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation of the Visit."""
        return f"<Visit(id={self.id}, client_id={self.client_id}, scheduled_at={self.scheduled_at}, status={self.status})>"

