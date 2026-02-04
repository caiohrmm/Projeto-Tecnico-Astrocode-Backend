"""User management routes (for managers only)."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_manager
from app.db import get_db
from app.users.models import User
from app.users.repository import UserRepository
from app.users.role_repository import RoleRepository
from app.users.schemas import UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.put(
    "/{user_id}/roles",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def update_user_roles(
    user_id: uuid.UUID,
    role_names: List[str],
    db: Session = Depends(get_db),
    current_manager: User = Depends(get_current_manager),
) -> UserResponse:
    """
    Update user roles (only managers can perform this action).

    This endpoint allows managers to assign or change roles for any user.
    Valid roles: 'atendente', 'corretor', 'gestor'

    Args:
        user_id: UUID of the user to update
        role_names: List of role names to assign (e.g., ['atendente', 'corretor'])
        db: Database session
        current_manager: Current authenticated manager (gestor role required)

    Returns:
        Updated user information with new roles

    Raises:
        HTTPException: If user not found, invalid roles, or current user is not a manager
    """
    user_repo = UserRepository(db)
    role_repo = RoleRepository(db)

    # Get user to update
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Validate role names
    valid_roles = ["atendente", "corretor", "gestor"]
    invalid_roles = [role for role in role_names if role not in valid_roles]
    if invalid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role names: {invalid_roles}. Valid roles are: {valid_roles}",
        )

    # Check if all roles exist in database
    existing_roles = role_repo.get_by_names(role_names)
    existing_role_names = [role.name for role in existing_roles]
    missing_roles = [role for role in role_names if role not in existing_role_names]
    if missing_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Roles not found in database: {missing_roles}",
        )

    # Update user roles
    updated_user = user_repo.assign_roles(user, role_names)

    return UserResponse.model_validate(updated_user)


@router.get(
    "/",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
)
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_manager: User = Depends(get_current_manager),
) -> List[UserResponse]:
    """
    List all users (only managers can perform this action).

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        current_manager: Current authenticated manager (gestor role required)

    Returns:
        List of user information
    """
    user_repo = UserRepository(db)
    users = user_repo.get_all(skip=skip, limit=limit)
    return [UserResponse.model_validate(user) for user in users]


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_manager: User = Depends(get_current_manager),
) -> UserResponse:
    """
    Get user by ID (only managers can perform this action).

    Args:
        user_id: UUID of the user
        db: Database session
        current_manager: Current authenticated manager (gestor role required)

    Returns:
        User information

    Raises:
        HTTPException: If user not found
    """
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def update_user(
    user_id: uuid.UUID,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_manager: User = Depends(get_current_manager),
) -> UserResponse:
    """
    Update user information (only managers can perform this action).

    This endpoint allows managers to update user information including:
    - Email
    - Full name
    - Active status (is_active)

    Args:
        user_id: UUID of the user to update
        user_data: User update data (all fields optional)
        db: Database session
        current_manager: Current authenticated manager (gestor role required)

    Returns:
        Updated user information

    Raises:
        HTTPException: If user not found or current user is not a manager
    """
    user_repo = UserRepository(db)

    # Get user to update
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent manager from deactivating themselves
    if user_data.is_active is False and user.id == current_manager.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    # Update user
    updated_user = user_repo.update(user, user_data)

    return UserResponse.model_validate(updated_user)

