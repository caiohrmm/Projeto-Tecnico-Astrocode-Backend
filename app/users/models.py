"""User model for authentication and authorization."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# Association table for many-to-many relationship between User and Role
user_roles = Table(
    "user_roles",
    Base.metadata,
    mapped_column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    mapped_column("role_id", UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
)


class User(Base):
    """
    User model representing system users.

    Attributes:
        id: Unique identifier (UUID)
        email: User email address (unique, indexed)
        hashed_password: Hashed password for authentication
        full_name: User's full name
        is_active: Whether the user account is active
        created_at: Timestamp when the user was created
        updated_at: Timestamp when the user was last updated
        roles: Associated roles (many-to-many relationship)
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
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

    # Relationship to roles (many-to-many)
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",  # Eager load roles when user is loaded
    )

    def __repr__(self) -> str:
        """String representation of the User."""
        return f"<User(id={self.id}, email={self.email}, full_name={self.full_name})>"


class Role(Base):
    """
    Role model for role-based access control.

    Attributes:
        id: Unique identifier (UUID)
        name: Role name (unique, e.g., atendente, corretor, gestor)
        description: Optional role description
        created_at: Timestamp when the role was created
        updated_at: Timestamp when the role was last updated
        users: Associated users (many-to-many relationship)
    """

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(500),
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

    # Relationship to users (many-to-many)
    users: Mapped[list["User"]] = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation of the Role."""
        return f"<Role(id={self.id}, name={self.name})>"
