"""Authentication routes."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.auth.oauth_service import OAuthService
from app.auth.schemas import LoginRequest, TokenResponse
from app.auth.service import AuthService
from app.db import get_db
from app.users.models import User
from app.users.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate user and return JWT token.

    Args:
        login_data: Login credentials (email and password)
        db: Database session

    Returns:
        JWT access token and token type

    Raises:
        HTTPException: If credentials are invalid
    """
    auth_service = AuthService(db)
    token_data = auth_service.authenticate_user(
        email=login_data.email,
        password=login_data.password,
    )
    return TokenResponse(**token_data)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """
    Get current authenticated user information.

    Args:
        current_user: Current authenticated user from dependency

    Returns:
        Current user information
    """
    return UserResponse.model_validate(current_user)


# Google OAuth routes
@router.get("/google/login")
async def google_login(
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Initiate Google OAuth login flow.

    Redirects user to Google authorization page.

    Returns:
        Redirect response to Google OAuth authorization URL
    """
    oauth_service = OAuthService(db)

    # Use redirect URI from settings (must match Google Cloud Console exactly)
    authorization_url, _ = await oauth_service.get_google_authorization_url()

    return RedirectResponse(url=authorization_url)


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str | None = None,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Handle Google OAuth callback.

    Args:
        code: Authorization code from Google
        state: State parameter for CSRF protection
        db: Database session

    Returns:
        JWT access token response
    """
    oauth_service = OAuthService(db)
    return await oauth_service.handle_google_callback(code=code, state=state)

