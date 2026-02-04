"""AI Summary routes for viewing and managing AI summaries."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.ai.models import AISummary, AISummaryStatus
from app.ai.repository import AISummaryRepository
from app.ai.schemas import AISummaryResponse, AISummaryUpdate
from app.db import get_db
from app.users.models import User

router = APIRouter(prefix="/ai/summaries", tags=["ai-summaries"])


@router.get("/", response_model=List[AISummaryResponse])
def list_ai_summaries(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    client_id: uuid.UUID | None = Query(None, description="Filter by client ID"),
    status: AISummaryStatus | None = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[AISummaryResponse]:
    """
    List all AI summaries with optional filtering and pagination.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        client_id: Optional filter by client ID
        status: Optional filter by status
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of AI summary responses
    """
    ai_repo = AISummaryRepository(db)
    summaries = ai_repo.get_all(
        skip=skip,
        limit=limit,
        client_id=client_id,
        status=status,
    )
    return [AISummaryResponse.model_validate(summary) for summary in summaries]


@router.get("/{summary_id}", response_model=AISummaryResponse)
def get_ai_summary(
    summary_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AISummaryResponse:
    """
    Get an AI summary by ID.

    Args:
        summary_id: AI summary UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        AI summary response

    Raises:
        HTTPException: If summary is not found
    """
    ai_repo = AISummaryRepository(db)
    summary = ai_repo.get_by_id(summary_id)

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI summary with ID {summary_id} not found",
        )

    return AISummaryResponse.model_validate(summary)


@router.get("/attendance/{attendance_id}", response_model=AISummaryResponse)
def get_ai_summary_by_attendance(
    attendance_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AISummaryResponse:
    """
    Get AI summary by attendance ID.

    Args:
        attendance_id: Attendance UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        AI summary response

    Raises:
        HTTPException: If summary is not found
    """
    ai_repo = AISummaryRepository(db)
    summary = ai_repo.get_by_attendance_id(attendance_id)

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI summary for attendance {attendance_id} not found",
        )

    return AISummaryResponse.model_validate(summary)


@router.get("/client/{client_id}", response_model=List[AISummaryResponse])
def get_ai_summaries_by_client(
    client_id: uuid.UUID,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[AISummaryResponse]:
    """
    Get all AI summaries for a specific client.

    Args:
        client_id: Client UUID
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of AI summary responses for the client
    """
    ai_repo = AISummaryRepository(db)
    summaries = ai_repo.get_by_client_id(
        client_id=client_id,
        skip=skip,
        limit=limit,
    )
    return [AISummaryResponse.model_validate(summary) for summary in summaries]


@router.put("/{summary_id}", response_model=AISummaryResponse)
def update_ai_summary(
    summary_id: uuid.UUID,
    summary_data: AISummaryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AISummaryResponse:
    """
    Update an AI summary (useful for reprocessing or manual corrections).

    Args:
        summary_id: AI summary UUID
        summary_data: AI summary update data (only provided fields will be updated)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated AI summary response

    Raises:
        HTTPException: If summary is not found
    """
    ai_repo = AISummaryRepository(db)
    summary = ai_repo.get_by_id(summary_id)

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI summary with ID {summary_id} not found",
        )

    updated_summary = ai_repo.update(summary, summary_data)
    return AISummaryResponse.model_validate(updated_summary)


@router.delete("/{summary_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ai_summary(
    summary_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """
    Delete an AI summary.

    Args:
        summary_id: AI summary UUID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If summary is not found
    """
    ai_repo = AISummaryRepository(db)
    summary = ai_repo.get_by_id(summary_id)

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI summary with ID {summary_id} not found",
        )

    ai_repo.delete(summary)


