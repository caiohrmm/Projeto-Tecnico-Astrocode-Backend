"""Pydantic schemas for Losses."""

import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from app.losses.models import LossReason, LossStage


class LossBase(BaseModel):
    """Base schema for Loss."""

    client_id: uuid.UUID = Field(..., description="ID do cliente")
    property_id: uuid.UUID | None = Field(None, description="ID do imóvel (se aplicável)")
    broker_id: uuid.UUID | None = Field(None, description="ID do corretor")

    loss_reason: LossReason = Field(..., description="Motivo principal da perda (enum LossReason)")
    loss_stage: LossStage = Field(..., description="Estágio em que o cliente foi perdido (enum LossStage)")

    detailed_reason: str | None = Field(None, description="Explicação detalhada")
    client_feedback: str | None = Field(None, description="Feedback do cliente")
    competitor_info: str | None = Field(None, description="Informação sobre concorrência")

    could_have_been_prevented: bool | None = Field(None, description="Poderia ter sido evitado?")
    lessons_learned: str | None = Field(None, description="Lições aprendidas")


class LossCreate(LossBase):
    """Schema for creating a loss record."""
    pass


class LossUpdate(BaseModel):
    """Schema for updating a loss record. All fields optional."""

    loss_reason: LossReason | None = Field(None, description="Motivo da perda")
    loss_stage: LossStage | None = Field(None, description="Estágio da perda")
    detailed_reason: str | None = Field(None, description="Explicação detalhada")
    client_feedback: str | None = Field(None, description="Feedback do cliente")
    competitor_info: str | None = Field(None, description="Informação sobre concorrência")
    could_have_been_prevented: bool | None = Field(None, description="Poderia ter sido evitado?")
    lessons_learned: str | None = Field(None, description="Lições aprendidas")


class LossResponse(LossBase):
    """Schema for loss response (inclui nomes de cliente, imóvel e corretor)."""

    id: uuid.UUID = Field(..., description="UUID da perda")
    ai_analysis: str | None = Field(None, description="Análise da perda pela IA (preenchida em background)")
    ai_recommendations: str | None = Field(None, description="Recomendações da IA")
    lost_at: datetime = Field(..., description="Data/hora em que a perda foi registrada")
    created_at: datetime = Field(..., description="Data de criação do registro")

    # Related entity names
    client_name: str | None = Field(None, description="Nome do cliente")
    property_title: str | None = Field(None, description="Título do imóvel")
    broker_name: str | None = Field(None, description="Nome do corretor")

    class Config:
        from_attributes = True


class LossPatternAnalysis(BaseModel):
    """Análise de padrões de perda gerada pela IA."""

    total_losses: int = Field(0, description="Total de perdas no período")
    period_analyzed: str = Field("", description="Descrição do período analisado")

    top_reasons: List[dict] = Field(default_factory=list, description="Motivos mais frequentes com contagem")
    critical_stages: List[dict] = Field(default_factory=list, description="Estágios com mais perdas")
    patterns_detected: List[str] = Field(default_factory=list, description="Padrões detectados pela IA")
    recommendations: List[str] = Field(default_factory=list, description="Recomendações para reduzir perdas")
    risk_factors: List[str] = Field(default_factory=list, description="Fatores de risco identificados")
    success_vs_loss_insights: str | None = Field(None, description="Comparação com negócios ganhos")
    summary: str = Field("", description="Resumo geral da análise")


class LossStats(BaseModel):
    """Estatísticas agregadas de perdas."""

    total_losses: int = Field(0, description="Total de perdas")
    losses_by_reason: dict = Field(default_factory=dict, description="Perdas agrupadas por motivo")
    losses_by_stage: dict = Field(default_factory=dict, description="Perdas agrupadas por estágio")
    preventable_count: int = Field(0, description="Quantidade marcada como evitável")
    avg_days_to_loss: float = Field(0.0, description="Média de dias até a perda")
    monthly_losses: List[dict] = Field(default_factory=list, description="Tendência mensal (lista de {month, count, ...})")

