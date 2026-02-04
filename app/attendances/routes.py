"""Attendance routes for CRUD operations."""

import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.attendances.models import Attendance, AttendanceChannel, AttendanceStatus
from app.attendances.repository import AttendanceRepository
from app.attendances.schemas import AttendanceCreate, AttendanceResponse, AttendanceUpdate
from app.db import get_db
from app.users.models import User
from app.users.repository import UserRepository

router = APIRouter(prefix="/attendances", tags=["attendances"])


def _validate_agent_is_corretor(agent_id: uuid.UUID, db: Session) -> None:
    """
    Validate that agent_id belongs to a user with 'corretor' role.

    Args:
        agent_id: UUID of the agent to validate
        db: Database session

    Raises:
        HTTPException: If agent_id is provided but user doesn't have 'corretor' role
    """
    user_repo = UserRepository(db)
    agent = user_repo.get_by_id(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {agent_id} not found",
        )

    # Check if user has 'corretor' role
    role_names = [role.name for role in agent.roles]
    if "corretor" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User {agent_id} does not have 'corretor' role. Only users with 'corretor' role can be assigned as agents.",
        )


@router.post("/", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
def create_attendance(
    attendance_data: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AttendanceResponse:
    """
    Create a new attendance.

    Duration is calculated automatically when ended_at is provided.
    If updated_client_status is provided, client status will be updated.
    If scheduled_visit_at is provided, a visit will be created automatically.

    Args:
        attendance_data: Attendance creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created attendance response
    """
    # Validate agent_id must be a corretor
    _validate_agent_is_corretor(attendance_data.agent_id, db)

    attendance_repo = AttendanceRepository(db)
    attendance = attendance_repo.create(attendance_data)
    return AttendanceResponse.model_validate(attendance)


@router.get("/", response_model=List[AttendanceResponse])
def list_attendances(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    client_id: uuid.UUID | None = Query(None, description="Filter by client ID"),
    agent_id: uuid.UUID | None = Query(None, description="Filter by agent ID"),
    property_id: uuid.UUID | None = Query(None, description="Filter by property ID"),
    channel: AttendanceChannel | None = Query(None, description="Filter by channel"),
    status: AttendanceStatus | None = Query(None, description="Filter by status"),
    started_from: datetime | None = Query(None, description="Filter by started date (from)"),
    started_to: datetime | None = Query(None, description="Filter by started date (to)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[AttendanceResponse]:
    """
    List all attendances with optional filtering and pagination.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        client_id: Optional filter by client ID
        agent_id: Optional filter by agent ID
        property_id: Optional filter by property ID
        channel: Optional filter by channel
        status: Optional filter by status
        started_from: Optional filter by started date (from)
        started_to: Optional filter by started date (to)
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of attendance responses
    """
    attendance_repo = AttendanceRepository(db)
    attendances = attendance_repo.get_all(
        skip=skip,
        limit=limit,
        client_id=client_id,
        agent_id=agent_id,
        property_id=property_id,
        channel=channel,
        status=status,
        started_from=started_from,
        started_to=started_to,
    )
    return [AttendanceResponse.model_validate(attendance) for attendance in attendances]


@router.get("/{attendance_id}", response_model=AttendanceResponse)
def get_attendance(
    attendance_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AttendanceResponse:
    """
    Get an attendance by ID.

    Args:
        attendance_id: Attendance UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Attendance response

    Raises:
        HTTPException: If attendance is not found
    """
    attendance_repo = AttendanceRepository(db)
    attendance = attendance_repo.get_by_id(attendance_id)

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance with ID {attendance_id} not found",
        )

    return AttendanceResponse.model_validate(attendance)


@router.put("/{attendance_id}", response_model=AttendanceResponse)
def update_attendance(
    attendance_id: uuid.UUID,
    attendance_data: AttendanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AttendanceResponse:
    """
    Update an attendance.

    Duration is recalculated automatically if ended_at is updated.
    If updated_client_status is provided, client status will be updated.
    If scheduled_visit_at is provided and not already set, a visit will be created.

    Args:
        attendance_id: Attendance UUID
        attendance_data: Attendance update data (only provided fields will be updated)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated attendance response

    Raises:
        HTTPException: If attendance is not found
    """
    # Validate agent_id if being updated
    if attendance_data.agent_id is not None:
        _validate_agent_is_corretor(attendance_data.agent_id, db)

    attendance_repo = AttendanceRepository(db)
    attendance = attendance_repo.get_by_id(attendance_id)

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance with ID {attendance_id} not found",
        )

    updated_attendance = attendance_repo.update(attendance, attendance_data)
    return AttendanceResponse.model_validate(updated_attendance)


@router.delete("/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(
    attendance_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """
    Delete an attendance.

    Args:
        attendance_id: Attendance UUID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If attendance is not found
    """
    attendance_repo = AttendanceRepository(db)
    attendance = attendance_repo.get_by_id(attendance_id)

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance with ID {attendance_id} not found",
        )

    attendance_repo.delete(attendance)

