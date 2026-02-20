"""Pydantic schemas for authentication."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Credenciais de login."""

    email: EmailStr = Field(..., description="E-mail do usuário")
    password: str = Field(..., min_length=1, description="Senha")


class TokenResponse(BaseModel):
    """Resposta com token JWT para uso no header Authorization."""

    access_token: str = Field(..., description="Token JWT")
    token_type: str = Field(default="bearer", description="Tipo do token (sempre bearer)")


class ForgotPasswordRequest(BaseModel):
    """Solicitação de recuperação de senha."""

    email: EmailStr = Field(..., description="E-mail do usuário que esqueceu a senha")


class ResetPasswordRequest(BaseModel):
    """Dados para redefinir a senha (link do e-mail)."""

    token: str = Field(..., min_length=1, description="Token recebido por e-mail")
    new_password: str = Field(..., min_length=6, description="Nova senha (mín. 6 caracteres)")


class ForgotPasswordResponse(BaseModel):
    """Resposta genérica por segurança (não revela se o e-mail existe)."""

    message: str = Field(
        default="Se o email existir em nossa base, você receberá um link para redefinir sua senha.",
        description="Mensagem exibida ao usuário",
    )


class ResetPasswordResponse(BaseModel):
    """Confirmação de senha alterada."""

    message: str = Field(
        default="Senha alterada com sucesso. Faça login com a nova senha.",
        description="Mensagem de sucesso",
    )


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

