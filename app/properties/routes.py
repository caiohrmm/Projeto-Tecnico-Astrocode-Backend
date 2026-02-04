"""Property routes for CRUD operations."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db import get_db
from app.properties.models import BusinessType, Property, PropertyStatus, PropertyType
from app.properties.repository import PropertyRepository
from app.properties.schemas import PropertyCreate, PropertyResponse, PropertyUpdate
from app.users.models import User
from app.users.repository import UserRepository

router = APIRouter(prefix="/properties", tags=["properties"])


def _validate_agent_is_corretor(assigned_agent_id: uuid.UUID | None, db: Session) -> None:
    """
    Validate that assigned_agent_id belongs to a user with 'corretor' role.

    Args:
        assigned_agent_id: UUID of the agent to validate
        db: Database session

    Raises:
        HTTPException: If agent_id is provided but user doesn't have 'corretor' role
    """
    if assigned_agent_id is None:
        return  # No validation needed if no agent is assigned

    user_repo = UserRepository(db)
    agent = user_repo.get_by_id(assigned_agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {assigned_agent_id} not found",
        )

    # Check if user has 'corretor' role
    role_names = [role.name for role in agent.roles]
    if "corretor" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User {assigned_agent_id} does not have 'corretor' role. Only users with 'corretor' role can be assigned as agents.",
        )


@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
def create_property(
    property_data: PropertyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PropertyResponse:
    """
    Create a new property.

    Args:
        property_data: Property creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created property response
    """
    # Validate assigned_agent_id if provided
    _validate_agent_is_corretor(property_data.assigned_agent_id, db)

    # Check if code already exists
    property_repo = PropertyRepository(db)
    existing_property = property_repo.get_by_code(property_data.code)
    if existing_property:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Property with code '{property_data.code}' already exists",
        )

    property = property_repo.create(property_data)
    return PropertyResponse.model_validate(property)


@router.get("/", response_model=List[PropertyResponse])
def list_properties(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    property_type: PropertyType | None = Query(None, description="Filter by property type"),
    business_type: BusinessType | None = Query(None, description="Filter by business type"),
    status: PropertyStatus | None = Query(None, description="Filter by status"),
    city: str | None = Query(None, description="Filter by city (partial match)"),
    state: str | None = Query(None, description="Filter by state (2 letters)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[PropertyResponse]:
    """
    List all properties with optional filtering and pagination.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        property_type: Optional filter by property type
        business_type: Optional filter by business type
        status: Optional filter by status
        city: Optional filter by city
        state: Optional filter by state
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of property responses
    """
    property_repo = PropertyRepository(db)
    properties = property_repo.get_all(
        skip=skip,
        limit=limit,
        property_type=property_type,
        business_type=business_type,
        status=status,
        city=city,
        state=state,
    )
    return [PropertyResponse.model_validate(prop) for prop in properties]


@router.get("/{property_id}", response_model=PropertyResponse)
def get_property(
    property_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PropertyResponse:
    """
    Get a property by ID.

    Args:
        property_id: Property UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Property response

    Raises:
        HTTPException: If property is not found
    """
    property_repo = PropertyRepository(db)
    property = property_repo.get_by_id(property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with ID {property_id} not found",
        )

    return PropertyResponse.model_validate(property)


@router.put("/{property_id}", response_model=PropertyResponse)
def update_property(
    property_id: uuid.UUID,
    property_data: PropertyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PropertyResponse:
    """
    Update a property.

    Args:
        property_id: Property UUID
        property_data: Property update data (only provided fields will be updated)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated property response

    Raises:
        HTTPException: If property is not found
    """
    # Validate assigned_agent_id if provided
    _validate_agent_is_corretor(property_data.assigned_agent_id, db)

    property_repo = PropertyRepository(db)
    property = property_repo.get_by_id(property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with ID {property_id} not found",
        )

    # Check if code is being updated and if it already exists
    if property_data.code is not None and property_data.code != property.code:
        existing_property = property_repo.get_by_code(property_data.code)
        if existing_property:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Property with code '{property_data.code}' already exists",
            )

    updated_property = property_repo.update(property, property_data)
    return PropertyResponse.model_validate(updated_property)


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(
    property_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """
    Delete a property.

    Args:
        property_id: Property UUID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If property is not found
    """
    property_repo = PropertyRepository(db)
    property = property_repo.get_by_id(property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with ID {property_id} not found",
        )

    property_repo.delete(property)

