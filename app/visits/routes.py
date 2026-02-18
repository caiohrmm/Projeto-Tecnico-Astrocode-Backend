"""Visit routes for CRUD operations."""

import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db import get_db
from app.users.repository import UserRepository
from app.visits.models import Visit, VisitStatus
from app.visits.repository import VisitRepository
from app.visits.schemas import VisitCreate, VisitResponse, VisitUpdate
from app.users.models import User
from app.attendances.repository import AttendanceRepository
from app.attendances.models import AttendanceStatus

router = APIRouter(prefix="/visits", tags=["visits"])


def _validate_broker_is_corretor(broker_id: uuid.UUID, db: Session) -> None:
    """
    Validate that broker_id belongs to a user with 'corretor' role.

    Args:
        broker_id: UUID of the broker to validate
        db: Database session

    Raises:
        HTTPException: If broker_id is provided but user doesn't have 'corretor' role
    """
    user_repo = UserRepository(db)
    broker = user_repo.get_by_id(broker_id)

    if not broker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {broker_id} not found",
        )

    # Check if user has 'corretor' role
    role_names = [role.name for role in broker.roles]
    if "corretor" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User {broker_id} does not have 'corretor' role. Only users with 'corretor' role can be assigned as brokers.",
        )


@router.post("/", response_model=VisitResponse, status_code=status.HTTP_201_CREATED)
def create_visit(
    visit_data: VisitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> VisitResponse:
    """
    Create a new visit.

    Args:
        visit_data: Visit creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created visit response
    """
    # Validate broker_id must be a corretor
    _validate_broker_is_corretor(visit_data.broker_id, db)

    # If visit is linked to an attendance, ensure attendance exists and is ACTIVE
    if visit_data.attendance_id is not None:
        attendance_repo = AttendanceRepository(db)
        attendance = attendance_repo.get_by_id(visit_data.attendance_id)

        if not attendance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attendance with ID {visit_data.attendance_id} not found",
            )

        if attendance.status != AttendanceStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Só é permitido criar visitas para atendimentos com status ACTIVE (Ativo).",
            )

    visit_repo = VisitRepository(db)
    visit = visit_repo.create(visit_data)
    return VisitResponse.model_validate(visit)


@router.get("/", response_model=List[VisitResponse])
def list_visits(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    client_id: uuid.UUID | None = Query(None, description="Filter by client ID"),
    broker_id: uuid.UUID | None = Query(None, description="Filter by broker ID"),
    property_id: uuid.UUID | None = Query(None, description="Filter by property ID"),
    status: VisitStatus | None = Query(None, description="Filter by status"),
    scheduled_from: datetime | None = Query(None, description="Filter by scheduled date (from)"),
    scheduled_to: datetime | None = Query(None, description="Filter by scheduled date (to)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[VisitResponse]:
    """
    List all visits with optional filtering and pagination.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        client_id: Optional filter by client ID
        broker_id: Optional filter by broker ID
        property_id: Optional filter by property ID
        status: Optional filter by status
        scheduled_from: Optional filter by scheduled date (from)
        scheduled_to: Optional filter by scheduled date (to)
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of visit responses
    """
    visit_repo = VisitRepository(db)
    visits = visit_repo.get_all(
        skip=skip,
        limit=limit,
        client_id=client_id,
        broker_id=broker_id,
        property_id=property_id,
        status=status,
        scheduled_from=scheduled_from,
        scheduled_to=scheduled_to,
    )
    return [VisitResponse.model_validate(visit) for visit in visits]


@router.get("/{visit_id}", response_model=VisitResponse)
def get_visit(
    visit_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> VisitResponse:
    """
    Get a visit by ID.

    Args:
        visit_id: Visit UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Visit response

    Raises:
        HTTPException: If visit is not found
    """
    visit_repo = VisitRepository(db)
    visit = visit_repo.get_by_id(visit_id)

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visit with ID {visit_id} not found",
        )

    return VisitResponse.model_validate(visit)


@router.put("/{visit_id}", response_model=VisitResponse)
def update_visit(
    visit_id: uuid.UUID,
    visit_data: VisitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> VisitResponse:
    """
    Update a visit.

    Args:
        visit_id: Visit UUID
        visit_data: Visit update data (only provided fields will be updated)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated visit response

    Raises:
        HTTPException: If visit is not found
    """
    # Validate broker_id if being updated
    if visit_data.broker_id is not None:
        _validate_broker_is_corretor(visit_data.broker_id, db)

    visit_repo = VisitRepository(db)
    visit = visit_repo.get_by_id(visit_id)

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visit with ID {visit_id} not found",
        )

    # If attendance_id is being updated, ensure attendance exists and is ACTIVE
    if visit_data.attendance_id is not None:
        attendance_repo = AttendanceRepository(db)
        attendance = attendance_repo.get_by_id(visit_data.attendance_id)

        if not attendance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attendance with ID {visit_data.attendance_id} not found",
            )

        if attendance.status != AttendanceStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Só é permitido vincular visitas a atendimentos com status ACTIVE (Ativo).",
            )

    updated_visit = visit_repo.update(visit, visit_data)
    return VisitResponse.model_validate(updated_visit)


@router.delete("/{visit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_visit(
    visit_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """
    Delete a visit.

    Args:
        visit_id: Visit UUID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If visit is not found
    """
    visit_repo = VisitRepository(db)
    visit = visit_repo.get_by_id(visit_id)

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visit with ID {visit_id} not found",
        )

    visit_repo.delete(visit)

