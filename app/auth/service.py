"""Authentication service for login and user management."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.auth.password import hash_password, verify_password
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

