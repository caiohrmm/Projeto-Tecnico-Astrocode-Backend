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


class ForgotPasswordRequest(BaseModel):
    """Schema for forgot password request."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Schema for reset password request."""

    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)


class ForgotPasswordResponse(BaseModel):
    """Schema for forgot password response (generic for security)."""

    message: str = "Se o email existir em nossa base, você receberá um link para redefinir sua senha."


class ResetPasswordResponse(BaseModel):
    """Schema for reset password response."""

    message: str = "Senha alterada com sucesso. Faça login com a nova senha."


class TokenData(BaseModel):
    """
    Schema for decoded token data.

    Attributes:
        user_id: User UUID from token
        email: User email from token
    """

    user_id: str | None = None
    email: str | None = None


# OAuth schemas
class OAuthProviderInfo(BaseModel):
    """
    Schema for OAuth provider information.

    Attributes:
        provider: Provider name (e.g., 'google')
        provider_user_id: User ID from the provider
        email: Email from the provider
        name: Full name from the provider
    """

    provider: str
    provider_user_id: str
    email: str
    name: str

