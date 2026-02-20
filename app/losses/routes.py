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


@router.post(
    "/",
    response_model=LossResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar perda de cliente",
    description="""
Registra a perda de um cliente (negócio não fechado).

**Efeitos automáticos:**
- **Cliente:** status atualizado para **LOST**.
- **Atendimento:** o atendimento ACTIVE do cliente é fechado com status **LOST**; o resumo da IA é regenerado e o lead score do cliente pode ser ajustado.
- **Timeline:** evento "Cliente perdido" adicionado na timeline do cliente.
- **IA:** análise da perda (ai_analysis, ai_recommendations) é disparada em background.

Requer autenticação.
    """.strip(),
    responses={
        201: {"description": "Perda registrada"},
        401: {"description": "Não autenticado"},
        404: {"description": "Cliente não encontrado"},
        422: {"description": "Dados inválidos"},
    },
)
def create_loss(
    loss_data: LossCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LossResponse:
    loss_repo = LossRepository(db)
    loss = loss_repo.create(loss_data)
    return LossResponse(**_enrich_loss_response(loss))


@router.get(
    "/",
    response_model=List[LossResponse],
    summary="Listar perdas",
    description="""
Lista registros de perda de clientes com paginação e filtros opcionais.

**Filtros:** client_id, broker_id, loss_reason, loss_stage, start_date, end_date. Resposta inclui nomes do cliente, imóvel e corretor.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Lista de perdas"},
        401: {"description": "Não autenticado"},
    },
)
def list_losses(
    skip: int = Query(0, ge=0, description="Registros a pular (paginação)"),
    limit: int = Query(100, ge=1, le=1000, description="Máximo de registros"),
    client_id: uuid.UUID | None = Query(None, description="Filtrar por cliente"),
    broker_id: uuid.UUID | None = Query(None, description="Filtrar por corretor"),
    loss_reason: LossReason | None = Query(None, description="Filtrar por motivo da perda"),
    loss_stage: LossStage | None = Query(None, description="Filtrar por estágio da perda"),
    start_date: datetime | None = Query(None, description="Data inicial"),
    end_date: datetime | None = Query(None, description="Data final"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[LossResponse]:
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


@router.get(
    "/stats",
    response_model=LossStats,
    summary="Estatísticas de perdas",
    description="""
Retorna estatísticas agregadas: total de perdas, por motivo, por estágio, quantidade evitáveis, média de dias até a perda, tendência mensal. Filtros opcionais: broker_id, start_date, end_date.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Estatísticas (LossStats)"},
        401: {"description": "Não autenticado"},
    },
)
def get_loss_stats(
    broker_id: uuid.UUID | None = Query(None, description="Filtrar por corretor"),
    start_date: datetime | None = Query(None, description="Data inicial"),
    end_date: datetime | None = Query(None, description="Data final"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LossStats:
    loss_repo = LossRepository(db)
    return loss_repo.get_stats(
        broker_id=broker_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/patterns",
    response_model=LossPatternAnalysis,
    summary="Análise de padrões de perda (IA)",
    description="""
Analisa padrões de perdas usando IA no período informado (days, entre 7 e 365; padrão 90).

**Retorno:** motivos mais frequentes, estágios críticos, padrões detectados, recomendações para reduzir perdas, fatores de risco e comparação com negócios ganhos (success_vs_loss_insights). Filtro opcional: broker_id.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Análise de padrões (LossPatternAnalysis)"},
        401: {"description": "Não autenticado"},
    },
)
def analyze_loss_patterns(
    broker_id: uuid.UUID | None = Query(None, description="Filtrar por corretor"),
    days: int = Query(90, ge=7, le=365, description="Dias para análise (7–365, padrão 90)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LossPatternAnalysis:
    loss_repo = LossRepository(db)
    return loss_repo.analyze_patterns(
        broker_id=broker_id,
        days=days,
    )


@router.get(
    "/{loss_id}",
    response_model=LossResponse,
    summary="Buscar perda por ID",
    description="Retorna um registro de perda pelo UUID. Inclui motivo, estágio, análise e recomendações da IA, nomes do cliente, imóvel e corretor.",
    responses={
        200: {"description": "Perda encontrada"},
        401: {"description": "Não autenticado"},
        404: {"description": "Perda não encontrada"},
    },
)
def get_loss(
    loss_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LossResponse:
    loss_repo = LossRepository(db)
    loss = loss_repo.get_by_id(loss_id)

    if not loss:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loss record not found",
        )

    return LossResponse(**_enrich_loss_response(loss))


@router.put(
    "/{loss_id}",
    response_model=LossResponse,
    summary="Atualizar perda",
    description="Atualização parcial: apenas os campos enviados são alterados. Não altera status do cliente (já LOST). Requer autenticação.",
    responses={
        200: {"description": "Perda atualizada"},
        401: {"description": "Não autenticado"},
        404: {"description": "Perda não encontrada"},
        422: {"description": "Dados inválidos"},
    },
)
def update_loss(
    loss_id: uuid.UUID,
    loss_data: LossUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LossResponse:
    loss_repo = LossRepository(db)
    loss = loss_repo.get_by_id(loss_id)

    if not loss:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loss record not found",
        )

    updated_loss = loss_repo.update(loss, loss_data)
    return LossResponse(**_enrich_loss_response(updated_loss))


@router.delete(
    "/{loss_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir perda",
    description="Remove o registro de perda do sistema. O status do cliente (LOST) não é alterado automaticamente. Operação irreversível. Requer autenticação.",
    responses={
        204: {"description": "Perda excluída"},
        401: {"description": "Não autenticado"},
        404: {"description": "Perda não encontrada"},
    },
)
def delete_loss(
    loss_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    loss_repo = LossRepository(db)
    loss = loss_repo.get_by_id(loss_id)

    if not loss:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loss record not found",
        )

    loss_repo.delete(loss)

