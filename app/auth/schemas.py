"""Pydantic schemas for authentication."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """
    Schema for login request.

    Attributes:
        email: User email address
        password: User password
    """

    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """
    Schema for token response.

    Attributes:
        access_token: JWT access token
        token_type: Token type (typically "bearer")
    """

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """
    Schema for decoded token data.

    Attributes:
        user_id: User UUID from token
        email: User email from token
    """

    user_id: str | None = None
    email: str | None = None

