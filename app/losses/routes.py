"""Losses routes for CRUD operations and pattern analysis."""

import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db import get_db
from app.losses.models import ClientLoss, LossReason, LossStage
from app.losses.repository import LossRepository
from app.losses.schemas import (
    LossCreate,
    LossPatternAnalysis,
    LossResponse,
    LossStats,
    LossUpdate,
)
from app.users.models import User

router = APIRouter(prefix="/losses", tags=["losses"])


def _enrich_loss_response(loss: ClientLoss) -> dict:
    """Enrich loss with related entity names."""
    return {
        "id": loss.id,
        "client_id": loss.client_id,
        "property_id": loss.property_id,
        "broker_id": loss.broker_id,
        "loss_reason": loss.loss_reason,
        "loss_stage": loss.loss_stage,
        "detailed_reason": loss.detailed_reason,
        "client_feedback": loss.client_feedback,
        "competitor_info": loss.competitor_info,
        "could_have_been_prevented": loss.could_have_been_prevented,
        "lessons_learned": loss.lessons_learned,
        "ai_analysis": loss.ai_analysis,
        "ai_recommendations": loss.ai_recommendations,
        "lost_at": loss.lost_at,
        "created_at": loss.created_at,
        # Enriched fields
        "client_name": loss.client.name if loss.client else None,
        "property_title": loss.property.title if loss.property else None,
        "broker_name": loss.broker.full_name if loss.broker else None,
    }


@router.post("/", response_model=LossResponse, status_code=status.HTTP_201_CREATED)
def create_loss(
    loss_data: LossCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LossResponse:
    """
    Register a lost client.

    This endpoint:
    - Creates the loss record with reason and stage
    - Updates client status to LOST
    - Adds timeline event
    - Triggers AI analysis of the loss
    """
    loss_repo = LossRepository(db)
    loss = loss_repo.create(loss_data)
    return LossResponse(**_enrich_loss_response(loss))


@router.get("/", response_model=List[LossResponse])
def list_losses(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    client_id: uuid.UUID | None = Query(None, description="Filter by client ID"),
    broker_id: uuid.UUID | None = Query(None, description="Filter by broker ID"),
    loss_reason: LossReason | None = Query(None, description="Filter by loss reason"),
    loss_stage: LossStage | None = Query(None, description="Filter by loss stage"),
    start_date: datetime | None = Query(None, description="Start date filter"),
    end_date: datetime | None = Query(None, description="End date filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[LossResponse]:
    """List all losses with optional filters."""
    loss_repo = LossRepository(db)
    losses = loss_repo.get_all(
        skip=skip,
        limit=limit,
        client_id=client_id,
        broker_id=broker_id,
        loss_reason=loss_reason,
        loss_stage=loss_stage,
        start_date=start_date,
        end_date=end_date,
    )
    return [LossResponse(**_enrich_loss_response(loss)) for loss in losses]


@router.get("/stats", response_model=LossStats)
def get_loss_stats(
    broker_id: uuid.UUID | None = Query(None, description="Filter by broker ID"),
    start_date: datetime | None = Query(None, description="Start date filter"),
    end_date: datetime | None = Query(None, description="End date filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LossStats:
    """Get loss statistics."""
    loss_repo = LossRepository(db)
    return loss_repo.get_stats(
        broker_id=broker_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/patterns", response_model=LossPatternAnalysis)
def analyze_loss_patterns(
    broker_id: uuid.UUID | None = Query(None, description="Filter by broker ID"),
    days: int = Query(90, ge=7, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LossPatternAnalysis:
    """
    Analyze loss patterns using AI.

    This endpoint uses AI to:
    - Identify recurring patterns in lost deals
    - Detect risk factors
    - Generate actionable recommendations
    - Compare with successful deals
    """
    loss_repo = LossRepository(db)
    return loss_repo.analyze_patterns(
        broker_id=broker_id,
        days=days,
    )


@router.get("/{loss_id}", response_model=LossResponse)
def get_loss(
    loss_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LossResponse:
    """Get a loss by ID with full details."""
    loss_repo = LossRepository(db)
    loss = loss_repo.get_by_id(loss_id)

    if not loss:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loss record not found",
        )

    return LossResponse(**_enrich_loss_response(loss))


@router.put("/{loss_id}", response_model=LossResponse)
def update_loss(
    loss_id: uuid.UUID,
    loss_data: LossUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LossResponse:
    """Update a loss record."""
    loss_repo = LossRepository(db)
    loss = loss_repo.get_by_id(loss_id)

    if not loss:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loss record not found",
        )

    updated_loss = loss_repo.update(loss, loss_data)
    return LossResponse(**_enrich_loss_response(updated_loss))


@router.delete("/{loss_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_loss(
    loss_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Delete a loss record."""
    loss_repo = LossRepository(db)
    loss = loss_repo.get_by_id(loss_id)

    if not loss:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loss record not found",
        )

    loss_repo.delete(loss)

