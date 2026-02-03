"""OAuth service for Google authentication."""

from typing import Any

from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.auth.models import AuthProvider
from app.auth.password import hash_password
from app.auth.schemas import OAuthProviderInfo, TokenResponse
from app.config.settings import get_settings
from app.users.models import User
from app.users.repository import UserRepository
from app.users.schemas import UserCreate

settings = get_settings()


class OAuthService:
    """Service for OAuth authentication operations."""

    def __init__(self, db: Session) -> None:
        """
        Initialize OAuth service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.user_repo = UserRepository(db)

    def get_google_oauth_client(self, redirect_uri: str | None = None) -> AsyncOAuth2Client:
        """
        Get Google OAuth2 client.

        Args:
            redirect_uri: Optional redirect URI override

        Returns:
            Configured OAuth2 client
        """
        redirect = redirect_uri or settings.google_redirect_uri

        return AsyncOAuth2Client(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=redirect,
        )

    async def get_google_authorization_url(
        self, redirect_uri: str | None = None
    ) -> tuple[str, str]:
        """
        Get Google OAuth authorization URL.

        Args:
            redirect_uri: Optional redirect URI override

        Returns:
            Tuple of (authorization_url, state)
        """
        client = self.get_google_oauth_client(redirect_uri)

        # Create authorization URL - authlib will generate state automatically
        authorization_url, state = client.create_authorization_url(
            url="https://accounts.google.com/o/oauth2/v2/auth",
            scope="openid email profile",
        )

        return authorization_url, state

    async def handle_google_callback(
        self, code: str, state: str | None = None
    ) -> TokenResponse:
        """
        Handle Google OAuth callback and authenticate user.

        Args:
            code: Authorization code from Google
            state: State parameter for CSRF protection

        Returns:
            Token response with JWT access token

        Raises:
            HTTPException: If OAuth flow fails or user cannot be created/authenticated
        """
        client = self.get_google_oauth_client()

        try:
            # Exchange code for token
            token_response = await client.fetch_token(
                "https://oauth2.googleapis.com/token",
                code=code,
            )

            # Get access token from response
            access_token = token_response.get("access_token")
            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to obtain access token from Google",
                )

            # Get user info from Google using the access token
            user_info = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_info.raise_for_status()
            google_data: dict[str, Any] = user_info.json()

            # Extract user information
            provider_info = OAuthProviderInfo(
                provider="google",
                provider_user_id=str(google_data.get("id", "")),
                email=google_data.get("email", ""),
                name=google_data.get("name", ""),
            )

            # Find or create user
            user = await self._find_or_create_user_from_oauth(provider_info)

            # Create JWT token
            token_data = {
                "sub": str(user.id),
                "email": user.email,
            }

            access_token = create_access_token(data=token_data)

            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
            )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OAuth authentication failed: {str(e)}",
            )

    async def _find_or_create_user_from_oauth(
        self, provider_info: OAuthProviderInfo
    ) -> User:
        """
        Find existing user or create new user from OAuth provider info.

        Args:
            provider_info: OAuth provider information

        Returns:
            User instance (existing or newly created)
        """
        # Check if auth provider already exists
        stmt = select(AuthProvider).where(
            AuthProvider.provider == provider_info.provider,
            AuthProvider.provider_user_id == provider_info.provider_user_id,
        )
        existing_provider = self.db.scalar(stmt)

        if existing_provider:
            # User already linked, return existing user
            user = existing_provider.user
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive",
                )
            return user

        # Check if user with same email exists
        existing_user = self.user_repo.get_by_email(provider_info.email)

        if existing_user:
            # Link OAuth provider to existing user
            auth_provider = AuthProvider(
                user_id=existing_user.id,
                provider=provider_info.provider,
                provider_user_id=provider_info.provider_user_id,
                provider_email=provider_info.email,
            )
            self.db.add(auth_provider)
            self.db.commit()
            self.db.refresh(existing_user)

            if not existing_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive",
                )

            return existing_user

        # Create new user
        # Note: For OAuth users, we use a placeholder password
        # They can only login via OAuth
        # Password must be <= 72 bytes for bcrypt
        placeholder_password = hash_password("oauth_placeholder")

        user_data = UserCreate(
            email=provider_info.email,
            password="placeholder",  # Not used, will be replaced by hashed placeholder
            full_name=provider_info.name,
        )

        user = self.user_repo.create(user_data, placeholder_password)

        # Assign default role 'atendente' to OAuth users
        # Manager can change this later via role management endpoint
        from app.users.role_repository import RoleRepository
        role_repo = RoleRepository(self.db)
        atendente_role = role_repo.get_by_name("atendente")
        
        if atendente_role:
            user.roles = [atendente_role]
            self.db.commit()

        # Link OAuth provider
        auth_provider = AuthProvider(
            user_id=user.id,
            provider=provider_info.provider,
            provider_user_id=provider_info.provider_user_id,
            provider_email=provider_info.email,
        )
        self.db.add(auth_provider)
        self.db.commit()
        self.db.refresh(user)

        return user

