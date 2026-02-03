"""Pydantic schemas for user validation and serialization."""

import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    """Base schema with common user fields."""

    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)


class UserCreate(UserBase):
    """
    Schema for creating a new user.

    Attributes:
        email: User email address
        password: Plain text password (will be hashed)
        full_name: User's full name
        role_names: Optional list of role names to assign to the user
    """

    password: str = Field(..., min_length=8, max_length=100)
    role_names: List[str] | None = Field(None, description="List of role names to assign")


class UserUpdate(BaseModel):
    """
    Schema for updating user information.

    All fields are optional to allow partial updates.
    """

    email: EmailStr | None = None
    full_name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = None


class UserResponse(UserBase):
    """
    Schema for user response (serialization).

    Excludes sensitive information like password.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    roles: List["RoleResponse"] = Field(default_factory=list)


class UserInDB(UserResponse):
    """
    Schema for user stored in database.

    Includes hashed_password for internal use.
    """

    hashed_password: str


# Role schemas
class RoleBase(BaseModel):
    """Base schema with common role fields."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class RoleCreate(RoleBase):
    """
    Schema for creating a new role.

    Attributes:
        name: Role name (must be unique)
        description: Optional role description
    """

    pass


class RoleUpdate(BaseModel):
    """
    Schema for updating role information.

    All fields are optional to allow partial updates.
    """

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class RoleResponse(RoleBase):
    """
    Schema for role response (serialization).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

