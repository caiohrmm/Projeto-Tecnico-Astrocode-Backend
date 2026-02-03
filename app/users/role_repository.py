"""Role repository for database operations."""

import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.users.models import Role
from app.users.schemas import RoleCreate, RoleUpdate


class RoleRepository:
    """Repository for role database operations."""

    def __init__(self, db: Session) -> None:
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create(self, role_data: RoleCreate) -> Role:
        """
        Create a new role.

        Args:
            role_data: Role creation data

        Returns:
            Created role instance
        """
        db_role = Role(
            name=role_data.name,
            description=role_data.description,
        )
        self.db.add(db_role)
        self.db.commit()
        self.db.refresh(db_role)
        return db_role

    def get_by_id(self, role_id: uuid.UUID) -> Role | None:
        """
        Get role by ID.

        Args:
            role_id: Role UUID

        Returns:
            Role instance or None if not found
        """
        stmt = select(Role).where(Role.id == role_id)
        return self.db.scalar(stmt)

    def get_by_name(self, name: str) -> Role | None:
        """
        Get role by name.

        Args:
            name: Role name

        Returns:
            Role instance or None if not found
        """
        stmt = select(Role).where(Role.name == name)
        return self.db.scalar(stmt)

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Role]:
        """
        Get all roles with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of role instances
        """
        stmt = select(Role).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_by_names(self, names: List[str]) -> List[Role]:
        """
        Get roles by list of names.

        Args:
            names: List of role names

        Returns:
            List of role instances
        """
        if not names:
            return []
        stmt = select(Role).where(Role.name.in_(names))
        return list(self.db.scalars(stmt).all())

    def update(
        self,
        role: Role,
        role_data: RoleUpdate,
    ) -> Role:
        """
        Update role information.

        Args:
            role: Role instance to update
            role_data: Update data (only provided fields will be updated)

        Returns:
            Updated role instance
        """
        update_data = role_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(role, field, value)

        self.db.commit()
        self.db.refresh(role)
        return role

    def delete(self, role: Role) -> None:
        """
        Delete a role.

        Args:
            role: Role instance to delete
        """
        self.db.delete(role)
        self.db.commit()

