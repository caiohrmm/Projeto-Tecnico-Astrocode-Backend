"""Authentication module."""

from app.auth.dependencies import get_current_active_user, get_current_user
from app.auth.jwt import create_access_token, decode_access_token
from app.auth.models import AuthProvider
from app.auth.oauth_service import OAuthService
from app.auth.password import hash_password, verify_password
from app.auth.routes import router as auth_router
from app.auth.schemas import LoginRequest, OAuthProviderInfo, TokenData, TokenResponse
from app.auth.service import AuthService

__all__ = [
    "AuthService",
    "OAuthService",
    "AuthProvider",
    "LoginRequest",
    "TokenResponse",
    "TokenData",
    "OAuthProviderInfo",
    "get_current_user",
    "get_current_active_user",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "auth_router",
]