"""User repository for database operations."""

import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.users.models import Role, User
from app.users.schemas import UserCreate, UserUpdate


class UserRepository:
    """Repository for user database operations."""

    def __init__(self, db: Session) -> None:
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create(self, user_data: UserCreate, hashed_password: str) -> User:
        """
        Create a new user.

        Args:
            user_data: User creation data
            hashed_password: Hashed password (should be hashed before calling)

        Returns:
            Created user instance
        """
        db_user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """
        Get user by ID.

        Args:
            user_id: User UUID

        Returns:
            User instance or None if not found
        """
        stmt = select(User).where(User.id == user_id)
        return self.db.scalar(stmt)

    def get_by_email(self, email: str) -> User | None:
        """
        Get user by email.

        Args:
            email: User email address

        Returns:
            User instance or None if not found
        """
        stmt = select(User).where(User.email == email)
        return self.db.scalar(stmt)

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[User]:
        """
        Get all users with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of user instances
        """
        stmt = select(User).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def update(
        self,
        user: User,
        user_data: UserUpdate,
    ) -> User:
        """
        Update user information.

        Args:
            user: User instance to update
            user_data: Update data (only provided fields will be updated)

        Returns:
            Updated user instance
        """
        update_data = user_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(user, field, value)

        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        """
        Delete a user.

        Args:
            user: User instance to delete
        """
        self.db.delete(user)
        self.db.commit()

    def assign_roles(self, user: User, role_names: List[str]) -> User:
        """
        Assign roles to a user by role names.

        Args:
            user: User instance
            role_names: List of role names to assign

        Returns:
            Updated user instance with roles assigned
        """
        if not role_names:
            return user

        stmt = select(Role).where(Role.name.in_(role_names))
        roles = list(self.db.scalars(stmt).all())

        # Clear existing roles and assign new ones
        user.roles = roles
        self.db.commit()
        self.db.refresh(user)
        return user

    def add_role(self, user: User, role_name: str) -> User:
        """
        Add a single role to a user.

        Args:
            user: User instance
            role_name: Role name to add

        Returns:
            Updated user instance
        """
        stmt = select(Role).where(Role.name == role_name)
        role = self.db.scalar(stmt)

        if role and role not in user.roles:
            user.roles.append(role)
            self.db.commit()
            self.db.refresh(user)

        return user

    def remove_role(self, user: User, role_name: str) -> User:
        """
        Remove a role from a user.

        Args:
            user: User instance
            role_name: Role name to remove

        Returns:
            Updated user instance
        """
        stmt = select(Role).where(Role.name == role_name)
        role = self.db.scalar(stmt)

        if role and role in user.roles:
            user.roles.remove(role)
            self.db.commit()
            self.db.refresh(user)

        return user

    def get_with_roles(self, user_id: uuid.UUID) -> User | None:
        """
        Get user by ID with roles eagerly loaded.

        Args:
            user_id: User UUID

        Returns:
            User instance with roles loaded or None if not found
        """
        stmt = select(User).where(User.id == user_id)
        user = self.db.scalar(stmt)
        if user:
            # Force eager load of roles
            _ = user.roles
        return user

