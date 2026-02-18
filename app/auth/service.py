"""Authentication service for login and user management."""

import secrets
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.auth.password import hash_password, verify_password
from app.config.settings import get_settings
from app.services.email_service import EmailService
from app.users.repository import UserRepository
from app.users.schemas import UserCreate


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: Session) -> None:
        """
        Initialize auth service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.user_repo = UserRepository(db)

    def authenticate_user(self, email: str, password: str) -> dict:
        """
        Authenticate a user with email and password.

        Args:
            email: User email address
            password: Plain text password

        Returns:
            Dictionary with access_token and token_type

        Raises:
            HTTPException: If credentials are invalid or user is inactive
        """
        # Normalize email (lowercase and strip whitespace)
        email = email.lower().strip()
        password = password.strip()

        # Get user by email
        user = self.user_repo.get_by_email(email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify password
        if not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        # Create access token
        token_data = {
            "sub": str(user.id),  # Subject (user ID)
            "email": user.email,
        }

        access_token = create_access_token(data=token_data)

        return {
            "access_token": access_token,
            "token_type": "bearer",
        }

    def register_user(self, user_data: UserCreate) -> dict:
        """
        Register a new user.

        Args:
            user_data: User creation data

        Returns:
            Dictionary with access_token and token_type

        Raises:
            HTTPException: If email already exists
        """
        # Check if user already exists
        existing_user = self.user_repo.get_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Hash password
        hashed_password = hash_password(user_data.password)

        # Create user
        user = self.user_repo.create(user_data, hashed_password)

        # Assign roles if provided
        if user_data.role_names:
            self.user_repo.assign_roles(user, user_data.role_names)

        # Create access token
        token_data = {
            "sub": str(user.id),
            "email": user.email,
        }

        access_token = create_access_token(data=token_data)

        return {
            "access_token": access_token,
            "token_type": "bearer",
        }

    def request_password_reset(self, email: str) -> None:
        """
        Request password reset for a user. Generates token, stores it, and sends email.

        Same response whether email exists or not (security - prevent enumeration).

        Args:
            email: User email address
        """
        email = email.lower().strip()
        user = self.user_repo.get_by_email(email)

        if user:
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

            self.user_repo.set_password_reset_token(user, token, expires_at)

            settings = get_settings()
            reset_link = f"{settings.frontend_url}/reset-password?token={token}"

            email_service = EmailService()
            email_service.send_password_reset_email(
                to_email=user.email,
                reset_link=reset_link,
                user_name=user.full_name,
            )

    def reset_password(self, token: str, new_password: str) -> None:
        """
        Reset user password using valid token.

        Args:
            token: Password reset token from email link
            new_password: New password to set

        Raises:
            HTTPException: If token is invalid or expired
        """
        user = self.user_repo.get_by_password_reset_token(token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Link inválido ou expirado. Solicite uma nova redefinição de senha.",
            )

        hashed_password = hash_password(new_password)
        user.hashed_password = hashed_password
        self.user_repo.set_password_reset_token(user, None, None)

