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
    """
    Enum for attendance status.
    
    Represents the lifecycle of a goal-oriented interaction cycle:
    - ACTIVE: Cycle is ongoing, objective not yet resolved
    - COMPLETED: Objective was successfully achieved (e.g., property purchased)
    - LOST: Objective was not achieved (e.g., client chose another option)
    - ABANDONED: Objective was abandoned (e.g., client lost interest, no response)
    """

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    LOST = "LOST"
    ABANDONED = "ABANDONED"


class Attendance(Base):
    """
    Attendance model representing a goal-oriented interaction cycle.

    An Attendance represents a decision cycle with a clear objective.
    It begins when the client expresses a clear objective and ends when
    that objective is resolved (won, lost, or abandoned).

    Attributes:
        id: Unique identifier (UUID)
        client_id: Foreign key to Client
        agent_id: Foreign key to User (real estate agent)
        property_id: Foreign key to Property (nullable)
        objective: Clear objective of this interaction cycle (e.g., "Purchase residential property in City X")
        channel: Communication channel (WHATSAPP, SITE, PHONE, EMAIL, IN_PERSON)
        raw_content: Raw content of conversations (can accumulate over time within the same cycle)
        ai_summary: AI-generated summary of the attendance cycle
        ai_next_steps: AI-generated next steps for the client
        status: Attendance status (ACTIVE, COMPLETED, LOST, ABANDONED)
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

    # Objective and content
    objective: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Clear objective of this interaction cycle (e.g., 'Purchase residential property in City X')",
    )
    raw_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Raw content of conversations (can accumulate over time within the same cycle)",
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
        default=AttendanceStatus.ACTIVE,
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

