"""FastAPI dependencies for authentication and authorization."""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.auth.schemas import TokenData
from app.db import get_db
from app.users.models import User
from app.users.repository import UserRepository

# Security scheme for Bearer token
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer token credentials
        db: Database session

    Returns:
        Current authenticated user

    Raises:
        HTTPException: If token is invalid, expired, or user not found
    """
    token = credentials.credentials

    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user ID from token
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get the current active user (alias for get_current_user).

    This dependency can be extended in the future to add additional
    checks if needed.

    Args:
        current_user: Current authenticated user

    Returns:
        Current active user
    """
    return current_user


def get_current_manager(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Get the current user and verify they have the 'gestor' role.

    Only users with the 'gestor' role can perform administrative actions
    like creating users and managing roles.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user with gestor role

    Raises:
        HTTPException: If user doesn't have 'gestor' role
    """
    # Check if user has 'gestor' role
    role_names = [role.name for role in current_user.roles]
    
    if "gestor" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers (gestor) can perform this action",
        )
    
    return current_user


def get_current_agent_or_manager(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Get the current user and verify they have 'corretor' or 'gestor' role.

    Only users with 'corretor' or 'gestor' roles can perform certain actions
    like deleting properties.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user with corretor or gestor role

    Raises:
        HTTPException: If user doesn't have 'corretor' or 'gestor' role
    """
    # Check if user has 'corretor' or 'gestor' role
    role_names = [role.name for role in current_user.roles]
    
    if "corretor" not in role_names and "gestor" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only agents (corretor) or managers (gestor) can perform this action. Attendees (atendente) cannot delete properties.",
        )
    
    return current_user

