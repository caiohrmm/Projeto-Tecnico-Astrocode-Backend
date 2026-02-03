"""Authentication provider models for OAuth integration."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuthProvider(Base):
    """
    Model for linking social authentication providers to users.

    Attributes:
        id: Unique identifier (UUID)
        user_id: Foreign key to users table
        provider: Provider name (e.g., 'google', 'facebook')
        provider_user_id: User ID from the provider
        provider_email: Email from the provider (may differ from user email)
        created_at: Timestamp when the link was created
        updated_at: Timestamp when the link was last updated
        user: Relationship to User model
    """

    __tablename__ = "auth_providers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    provider_user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    provider_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
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

    # Relationship to User
    user: Mapped["User"] = relationship(
        "User",
        back_populates="auth_providers",
        lazy="selectin",
    )

    # Unique constraint: one provider_user_id per provider
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_user_id"),
    )

    def __repr__(self) -> str:
        """String representation of the AuthProvider."""
        return (
            f"<AuthProvider(id={self.id}, provider={self.provider}, "
            f"provider_user_id={self.provider_user_id})>"
        )

