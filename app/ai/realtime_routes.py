"""Routes for real-time AI assistant during attendances."""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth.dependencies import get_current_user
from app.users.models import User
from app.ai.realtime_assistant import (
    realtime_assistant,
    RealTimeAnalysisResult,
    DetectedInfo,
    SuggestedQuestion,
    PropertySuggestion,
)

router = APIRouter(prefix="/ai/realtime", tags=["AI Real-time"])


class RealTimeAnalysisRequest(BaseModel):
    """Request for real-time analysis."""
    
    text: str = Field(..., min_length=1, max_length=10000)
    client_id: str | None = None
    include_properties: bool = True


class RealTimeAnalysisResponse(BaseModel):
    """Response from real-time analysis."""
    
    detected_info: list[dict] = Field(default_factory=list)
    property_suggestions: list[dict] = Field(default_factory=list)
    suggested_questions: list[dict] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    summary: str = ""
    detected_intent: str | None = None


@router.post("/analyze", response_model=RealTimeAnalysisResponse)
async def analyze_attendance_text(
    request: RealTimeAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RealTimeAnalysisResponse:
    """
    Analyze attendance text in real-time.
    
    Provides:
    - Detection of client information (budget, location, preferences)
    - Property suggestions based on detected interests
    - Suggested questions for the attendant
    - Alerts about important information
    """
    # Get client info if client_id provided
    client_name = None
    client_budget_min = None
    client_budget_max = None
    client_city_interest = None
    client_property_type = None
    client_interest_type = None
    
    if request.client_id:
        try:
            from app.clients.repository import ClientRepository
            client_repo = ClientRepository(db)
            client = client_repo.get_by_id(uuid.UUID(request.client_id))
            
            if client:
                client_name = client.name
                client_budget_min = client.current_budget_min
                client_budget_max = client.current_budget_max
                client_city_interest = client.current_city_interest
                if client.current_property_type:
                    client_property_type = client.current_property_type.value
                if client.current_interest_type:
                    client_interest_type = client.current_interest_type.value
        except (ValueError, Exception) as e:
            # Invalid client_id, continue without client context
            pass
    
    # Get available properties if requested
    available_properties = []
    if request.include_properties:
        try:
            from app.properties.repository import PropertyRepository
            from app.properties.schemas import PropertyListParams
            
            prop_repo = PropertyRepository(db)
            params = PropertyListParams(
                status="AVAILABLE",
                limit=50,
            )
            properties, _ = prop_repo.list(params)
            
            available_properties = [
                {
                    "id": str(p.id),
                    "title": p.title,
                    "city": p.city,
                    "price": p.price,
                    "rent_price": p.rent_price,
                    "property_type": p.property_type.value if p.property_type else None,
                    "bedrooms": p.bedrooms,
                    "area": p.area,
                }
                for p in properties
            ]
        except Exception as e:
            # Properties not available, continue without
            pass
    
    # Perform real-time analysis
    result = realtime_assistant.analyze_text(
        text=request.text,
        client_name=client_name,
        client_budget_min=client_budget_min,
        client_budget_max=client_budget_max,
        client_city_interest=client_city_interest,
        client_property_type=client_property_type,
        client_interest_type=client_interest_type,
        available_properties=available_properties,
    )
    
    # Convert to response format
    return RealTimeAnalysisResponse(
        detected_info=[
            {
                "field": info.field,
                "value": info.value,
                "confidence": info.confidence,
                "original_text": info.original_text,
            }
            for info in result.detected_info
        ],
        property_suggestions=[
            {
                "property_id": prop.property_id,
                "title": prop.title,
                "city": prop.city,
                "price": prop.price,
                "property_type": prop.property_type,
                "match_reason": prop.match_reason,
                "match_score": prop.match_score,
            }
            for prop in result.property_suggestions
        ],
        suggested_questions=[
            {
                "question": q.question,
                "reason": q.reason,
                "priority": q.priority,
                "category": q.category,
            }
            for q in result.suggested_questions
        ],
        alerts=result.alerts,
        summary=result.summary,
        detected_intent=result.detected_intent,
    )


@router.post("/quick-analysis")
async def quick_analyze(
    text: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Quick analysis without client context or property matching.
    Faster but less accurate.
    """
    result = realtime_assistant.analyze_text(text=text)
    
    return {
        "detected_info": [info.model_dump() for info in result.detected_info],
        "suggested_questions": [q.model_dump() for q in result.suggested_questions],
        "alerts": result.alerts,
        "summary": result.summary,
    }

