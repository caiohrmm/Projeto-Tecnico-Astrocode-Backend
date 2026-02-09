"""Pydantic schemas for Losses."""

import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from app.losses.models import LossReason, LossStage


class LossBase(BaseModel):
    """Base schema for Loss."""

    client_id: uuid.UUID = Field(..., description="Client ID (required)")
    property_id: uuid.UUID | None = Field(None, description="Property ID if applicable")
    broker_id: uuid.UUID | None = Field(None, description="Broker ID")
    
    loss_reason: LossReason = Field(..., description="Primary reason for loss")
    loss_stage: LossStage = Field(..., description="Stage at which client was lost")
    
    detailed_reason: str | None = Field(None, description="Detailed explanation")
    client_feedback: str | None = Field(None, description="Client's feedback")
    competitor_info: str | None = Field(None, description="Competitor information")
    
    could_have_been_prevented: bool | None = Field(None, description="Could this have been prevented?")
    lessons_learned: str | None = Field(None, description="Lessons learned")


class LossCreate(LossBase):
    """Schema for creating a loss record."""
    pass


class LossUpdate(BaseModel):
    """Schema for updating a loss record."""

    loss_reason: LossReason | None = None
    loss_stage: LossStage | None = None
    detailed_reason: str | None = None
    client_feedback: str | None = None
    competitor_info: str | None = None
    could_have_been_prevented: bool | None = None
    lessons_learned: str | None = None


class LossResponse(LossBase):
    """Schema for loss response."""

    id: uuid.UUID
    ai_analysis: str | None = None
    ai_recommendations: str | None = None
    lost_at: datetime
    created_at: datetime

    # Related entity names
    client_name: str | None = None
    property_title: str | None = None
    broker_name: str | None = None

    class Config:
        from_attributes = True


class LossPatternAnalysis(BaseModel):
    """Schema for AI-generated loss pattern analysis."""

    total_losses: int = 0
    period_analyzed: str = ""
    
    # Top reasons
    top_reasons: List[dict] = Field(default_factory=list, description="Most common loss reasons with counts")
    
    # Stage analysis
    critical_stages: List[dict] = Field(default_factory=list, description="Stages with most losses")
    
    # Pattern insights
    patterns_detected: List[str] = Field(default_factory=list, description="AI-detected patterns")
    
    # Recommendations
    recommendations: List[str] = Field(default_factory=list, description="AI recommendations to reduce losses")
    
    # Risk factors
    risk_factors: List[str] = Field(default_factory=list, description="Identified risk factors")
    
    # Success comparison
    success_vs_loss_insights: str | None = Field(None, description="Comparison with successful deals")
    
    # Overall summary
    summary: str = ""


class LossStats(BaseModel):
    """Schema for loss statistics."""

    total_losses: int = 0
    losses_by_reason: dict = Field(default_factory=dict)
    losses_by_stage: dict = Field(default_factory=dict)
    preventable_count: int = 0
    avg_days_to_loss: float = 0.0
    
    # Monthly trend
    monthly_losses: List[dict] = Field(default_factory=list)

