"""Pydantic schemas for user validation and serialization."""

import uuid
from datetime import datetime

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
    """

    password: str = Field(..., min_length=8, max_length=100)


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


class UserInDB(UserResponse):
    """
    Schema for user stored in database.

    Includes hashed_password for internal use.
    """

    hashed_password: str

