"""AI Journey routes for client journey analysis and timeline."""

import uuid
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db import get_db
from app.users.models import User
from app.ai.journey_service import ClientJourneyService, TimelineService
from app.clients.timeline_models import TimelineEventType

router = APIRouter(prefix="/ai/journey", tags=["ai-journey"])


# Pydantic schemas
class NextActionResponse(BaseModel):
    """Schema for next action suggestion."""
    priority: str
    action: str
    title: str
    description: str
    suggested_channel: str | None = None
    properties: list[str] | None = None


class JourneyInsightsResponse(BaseModel):
    """Schema for journey insights."""
    engagement_score: int
    relationship_health: str
    sentiment_trend: str
    lead_score_trend: str
    avg_ai_lead_score: float | None
    days_since_contact: int | None
    total_attendances: int
    completed_attendances: int
    total_visits: int
    completed_visits: int
    no_show_visits: int
    most_common_intent: str | None
    journey_stage: str


class JourneyAnalysisResponse(BaseModel):
    """Schema for AI journey analysis response."""
    analysis: str
    context_summary: dict[str, Any] | None = None
    next_actions: list[NextActionResponse]


class ClientContextResponse(BaseModel):
    """Schema for client context response."""
    client: dict[str, Any]
    attendances: list[dict[str, Any]]
    ai_summaries: list[dict[str, Any]]
    visits: list[dict[str, Any]]
    properties_of_interest: list[dict[str, Any]]
    timeline_summary: dict[str, Any]
    insights: JourneyInsightsResponse


class TimelineEventCreate(BaseModel):
    """Schema for creating timeline event."""
    event_type: TimelineEventType
    title: str = Field(..., max_length=255)
    description: str | None = None
    event_data: dict[str, Any] | None = None
    related_attendance_id: uuid.UUID | None = None
    related_visit_id: uuid.UUID | None = None
    related_property_id: uuid.UUID | None = None
    importance: int = Field(default=3, ge=1, le=5)


class TimelineEventResponse(BaseModel):
    """Schema for timeline event response."""
    id: uuid.UUID
    client_id: uuid.UUID
    event_type: str
    title: str
    description: str | None
    event_data: dict[str, Any] | None
    related_attendance_id: uuid.UUID | None
    related_visit_id: uuid.UUID | None
    related_property_id: uuid.UUID | None
    created_by_id: uuid.UUID | None
    ai_generated: bool
    importance: int
    created_at: str
    
    class Config:
        from_attributes = True


@router.get("/context/{client_id}", response_model=ClientContextResponse)
def get_client_context(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ClientContextResponse:
    """
    Get complete client context for AI analysis.
    
    This endpoint returns all relevant information about a client,
    including attendances, visits, AI summaries, and derived insights.
    
    Args:
        client_id: Client UUID
        
    Returns:
        Complete client context
    """
    context = ClientJourneyService.get_client_context(db, client_id)
    
    if "error" in context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=context["error"],
        )
    
    return context


@router.get("/analysis/{client_id}", response_model=JourneyAnalysisResponse)
def get_journey_analysis(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> JourneyAnalysisResponse:
    """
    Get AI-generated journey analysis for a client.
    
    Uses Gemini AI to analyze the complete client journey and provide:
    - Journey summary
    - Conversion probability
    - Points of attention
    - Recommended next steps
    - Approach strategy
    
    Args:
        client_id: Client UUID
        
    Returns:
        AI journey analysis with next actions
    """
    result = ClientJourneyService.generate_ai_journey_analysis(db, client_id)
    
    if "error" in result and result["error"] == "Client not found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    return result


@router.get("/next-actions/{client_id}", response_model=list[NextActionResponse])
def get_next_actions(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[NextActionResponse]:
    """
    Get AI-suggested next actions for a client.
    
    Returns prioritized list of suggested actions based on:
    - Current journey stage
    - Engagement level
    - Time since last contact
    - Visit history
    - AI insights
    
    Args:
        client_id: Client UUID
        
    Returns:
        List of suggested next actions
    """
    actions = ClientJourneyService.generate_next_actions(db, client_id)
    return actions


@router.get("/timeline/{client_id}", response_model=list[TimelineEventResponse])
def get_client_timeline(
    client_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    event_types: list[TimelineEventType] | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[TimelineEventResponse]:
    """
    Get timeline events for a client.
    
    Returns chronological list of all events in the client's journey.
    
    Args:
        client_id: Client UUID
        limit: Maximum events to return (default 50)
        event_types: Filter by specific event types
        
    Returns:
        List of timeline events
    """
    events = TimelineService.get_client_timeline(
        db, client_id, limit=limit, event_types=event_types
    )
    
    return [
        TimelineEventResponse(
            id=e.id,
            client_id=e.client_id,
            event_type=e.event_type.value,
            title=e.title,
            description=e.description,
            event_data=e.event_data,
            related_attendance_id=e.related_attendance_id,
            related_visit_id=e.related_visit_id,
            related_property_id=e.related_property_id,
            created_by_id=e.created_by_id,
            ai_generated=e.ai_generated,
            importance=e.importance,
            created_at=e.created_at.isoformat(),
        )
        for e in events
    ]


@router.post("/timeline/{client_id}", response_model=TimelineEventResponse, status_code=status.HTTP_201_CREATED)
def create_timeline_event(
    client_id: uuid.UUID,
    event_data: TimelineEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> TimelineEventResponse:
    """
    Create a new timeline event for a client.
    
    This allows manual addition of events to the client timeline.
    
    Args:
        client_id: Client UUID
        event_data: Event creation data
        
    Returns:
        Created timeline event
    """
    event = TimelineService.add_event(
        db=db,
        client_id=client_id,
        event_type=event_data.event_type,
        title=event_data.title,
        description=event_data.description,
        event_data=event_data.event_data,
        related_attendance_id=event_data.related_attendance_id,
        related_visit_id=event_data.related_visit_id,
        related_property_id=event_data.related_property_id,
        created_by_id=current_user.id,
        ai_generated=False,
        importance=event_data.importance,
    )
    
    return TimelineEventResponse(
        id=event.id,
        client_id=event.client_id,
        event_type=event.event_type.value,
        title=event.title,
        description=event.description,
        event_data=event.event_data,
        related_attendance_id=event.related_attendance_id,
        related_visit_id=event.related_visit_id,
        related_property_id=event.related_property_id,
        created_by_id=event.created_by_id,
        ai_generated=event.ai_generated,
        importance=event.importance,
        created_at=event.created_at.isoformat(),
    )


@router.get("/insights/{client_id}", response_model=JourneyInsightsResponse)
def get_journey_insights(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> JourneyInsightsResponse:
    """
    Get computed insights for a client's journey.
    
    Returns metrics and trends calculated from client data:
    - Engagement score
    - Relationship health
    - Sentiment/lead score trends
    - Journey stage
    
    Args:
        client_id: Client UUID
        
    Returns:
        Journey insights
    """
    context = ClientJourneyService.get_client_context(db, client_id)
    
    if "error" in context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=context["error"],
        )
    
    return context["insights"]

