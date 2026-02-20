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
    """Sugestão de próxima ação (IA)."""

    priority: str = Field(..., description="Prioridade (ex.: high, medium)")
    action: str = Field(..., description="Tipo de ação")
    title: str = Field(..., description="Título")
    description: str = Field(..., description="Descrição")
    suggested_channel: str | None = Field(None, description="Canal sugerido (ex.: WhatsApp)")
    properties: list[str] | None = Field(None, description="IDs de imóveis relacionados")


class JourneyInsightsResponse(BaseModel):
    """Métricas e tendências calculadas da jornada do cliente."""

    engagement_score: int = Field(..., description="Score de engajamento")
    relationship_health: str = Field(..., description="Saúde do relacionamento")
    sentiment_trend: str = Field(..., description="Tendência de sentimento")
    lead_score_trend: str = Field(..., description="Tendência do lead score")
    avg_ai_lead_score: float | None = Field(None, description="Média do lead score (IA)")
    days_since_contact: int | None = Field(None, description="Dias desde último contato")
    total_attendances: int = Field(..., description="Total de atendimentos")
    completed_attendances: int = Field(..., description="Atendimentos concluídos")
    total_visits: int = Field(..., description="Total de visitas")
    completed_visits: int = Field(..., description="Visitas realizadas")
    no_show_visits: int = Field(..., description="Visitas no-show")
    most_common_intent: str | None = Field(None, description="Intenção mais comum")
    journey_stage: str = Field(..., description="Estágio da jornada")


class JourneyAnalysisResponse(BaseModel):
    """Resposta da análise de jornada pela IA (Gemini)."""

    analysis: str = Field(..., description="Texto da análise (resumo, probabilidade de conversão, estratégia)")
    context_summary: dict[str, Any] | None = Field(None, description="Resumo do contexto")
    next_actions: list[NextActionResponse] = Field(..., description="Próximas ações recomendadas")


class ClientContextResponse(BaseModel):
    """Contexto completo do cliente (cliente, atendimentos, resumos IA, visitas, imóveis, insights)."""

    client: dict[str, Any] = Field(..., description="Dados do cliente")
    attendances: list[dict[str, Any]] = Field(..., description="Atendimentos")
    ai_summaries: list[dict[str, Any]] = Field(..., description="Resumos IA")
    visits: list[dict[str, Any]] = Field(..., description="Visitas")
    properties_of_interest: list[dict[str, Any]] = Field(..., description="Imóveis de interesse")
    timeline_summary: dict[str, Any] = Field(..., description="Resumo da timeline")
    insights: JourneyInsightsResponse = Field(..., description="Insights calculados")


class TimelineEventCreate(BaseModel):
    """Payload para criar evento manual na timeline."""

    event_type: TimelineEventType = Field(..., description="Tipo do evento (enum TimelineEventType)")
    title: str = Field(..., max_length=255, description="Título do evento")
    description: str | None = Field(None, description="Descrição")
    event_data: dict[str, Any] | None = Field(None, description="Dados adicionais (JSON)")
    related_attendance_id: uuid.UUID | None = Field(None, description="ID do atendimento relacionado")
    related_visit_id: uuid.UUID | None = Field(None, description="ID da visita relacionada")
    related_property_id: uuid.UUID | None = Field(None, description="ID do imóvel relacionado")
    importance: int = Field(default=3, ge=1, le=5, description="Importância 1–5 (padrão 3)")


class TimelineEventResponse(BaseModel):
    """Evento da timeline do cliente."""

    id: uuid.UUID = Field(..., description="UUID do evento")
    client_id: uuid.UUID = Field(..., description="ID do cliente")
    event_type: str = Field(..., description="Tipo do evento")
    title: str = Field(..., description="Título")
    description: str | None = Field(None, description="Descrição")
    event_data: dict[str, Any] | None = Field(None, description="Dados do evento")
    related_attendance_id: uuid.UUID | None = Field(None, description="Atendimento relacionado")
    related_visit_id: uuid.UUID | None = Field(None, description="Visita relacionada")
    related_property_id: uuid.UUID | None = Field(None, description="Imóvel relacionado")
    created_by_id: uuid.UUID | None = Field(None, description="Usuário que criou")
    ai_generated: bool = Field(..., description="Se foi gerado pela IA")
    importance: int = Field(..., description="Importância 1–5")
    created_at: str = Field(..., description="Data de criação (ISO)")

    class Config:
        from_attributes = True


@router.get(
    "/context/{client_id}",
    response_model=ClientContextResponse,
    summary="Contexto completo do cliente",
    description="""
Retorna o contexto completo do cliente para análise: dados do cliente, atendimentos, resumos IA, visitas, imóveis de interesse e insights calculados (engajamento, saúde do relacionamento, estágio da jornada, etc.). Base para análise de jornada e próximas ações.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Contexto do cliente (ClientContextResponse)"},
        401: {"description": "Não autenticado"},
        404: {"description": "Cliente não encontrado"},
    },
)
def get_client_context(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ClientContextResponse:
    context = ClientJourneyService.get_client_context(db, client_id)
    
    if "error" in context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=context["error"],
        )
    
    return context


@router.get(
    "/analysis/{client_id}",
    response_model=JourneyAnalysisResponse,
    summary="Análise de jornada (IA)",
    description="""
Gera análise da jornada do cliente pela IA (Gemini): resumo da jornada, probabilidade de conversão, pontos de atenção, próximos passos recomendados e estratégia de abordagem. Retorna analysis (texto), context_summary e next_actions.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Análise de jornada (JourneyAnalysisResponse)"},
        401: {"description": "Não autenticado"},
        404: {"description": "Cliente não encontrado"},
    },
)
def get_journey_analysis(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> JourneyAnalysisResponse:
    result = ClientJourneyService.generate_ai_journey_analysis(db, client_id)
    
    if "error" in result and result["error"] == "Client not found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    return result


@router.get(
    "/next-actions/{client_id}",
    response_model=list[NextActionResponse],
    summary="Próximas ações sugeridas (IA)",
    description="""
Retorna lista priorizada de ações sugeridas pela IA com base no estágio da jornada, nível de engajamento, tempo desde último contato, histórico de visitas e insights. Cada item inclui priority, action, title, description, suggested_channel e properties (IDs de imóveis se aplicável).

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Lista de próximas ações"},
        401: {"description": "Não autenticado"},
    },
)
def get_next_actions(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[NextActionResponse]:
    actions = ClientJourneyService.generate_next_actions(db, client_id)
    return actions


@router.get(
    "/timeline/{client_id}",
    response_model=list[TimelineEventResponse],
    summary="Timeline do cliente",
    description="""
Retorna a lista cronológica de eventos da jornada do cliente (até limit, padrão 50, máx. 200). Filtro opcional por event_types (ex.: STATUS_CHANGED, VISIT_SCHEDULED). Cada evento inclui tipo, título, descrição, dados, IDs relacionados e importance.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Lista de eventos da timeline"},
        401: {"description": "Não autenticado"},
    },
)
def get_client_timeline(
    client_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200, description="Máximo de eventos (1–200)"),
    event_types: list[TimelineEventType] | None = Query(default=None, description="Filtrar por tipos de evento"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[TimelineEventResponse]:
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


@router.post(
    "/timeline/{client_id}",
    response_model=TimelineEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar evento na timeline",
    description="""
Cria um evento manual na timeline do cliente. Campos: event_type, title (obrigatório), description, event_data (JSON), related_attendance_id, related_visit_id, related_property_id, importance (1–5, padrão 3). O evento é vinculado ao usuário atual (created_by_id).

Requer autenticação.
    """.strip(),
    responses={
        201: {"description": "Evento criado"},
        401: {"description": "Não autenticado"},
        404: {"description": "Cliente não encontrado"},
        422: {"description": "Dados inválidos"},
    },
)
def create_timeline_event(
    client_id: uuid.UUID,
    event_data: TimelineEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> TimelineEventResponse:
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


@router.get(
    "/insights/{client_id}",
    response_model=JourneyInsightsResponse,
    summary="Insights da jornada",
    description="""
Retorna métricas e tendências calculadas a partir dos dados do cliente: engagement_score, relationship_health, sentiment_trend, lead_score_trend, dias desde último contato, totais de atendimentos/visitas (concluídos, no-show), intent mais comum e journey_stage.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Insights (JourneyInsightsResponse)"},
        401: {"description": "Não autenticado"},
        404: {"description": "Cliente não encontrado"},
    },
)
def get_journey_insights(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> JourneyInsightsResponse:
    context = ClientJourneyService.get_client_context(db, client_id)
    
    if "error" in context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=context["error"],
        )
    
    return context["insights"]

