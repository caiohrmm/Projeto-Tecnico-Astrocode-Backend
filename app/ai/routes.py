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


@router.get(
    "/",
    response_model=List[AISummaryResponse],
    summary="Listar resumos IA",
    description="""
Lista resumos gerados pela IA a partir dos atendimentos, com paginação e filtros. Cada resumo está vinculado a um atendimento (um por atendimento) e contém texto, pontos-chave, intenção detectada, interesse, orçamento, urgência, lead score sugerido e status (PENDING, PROCESSING, COMPLETED, FAILED, REPROCESSING).

Requer autenticação.
    """.strip(),
    responses={200: {"description": "Lista de resumos IA"}, 401: {"description": "Não autenticado"}},
)
def list_ai_summaries(
    skip: int = Query(0, ge=0, description="Registros a pular (paginação)"),
    limit: int = Query(100, ge=1, le=1000, description="Máximo de registros"),
    client_id: uuid.UUID | None = Query(None, description="Filtrar por cliente"),
    status: AISummaryStatus | None = Query(None, description="Filtrar por status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[AISummaryResponse]:
    ai_repo = AISummaryRepository(db)
    summaries = ai_repo.get_all(
        skip=skip,
        limit=limit,
        client_id=client_id,
        status=status,
    )
    return [AISummaryResponse.model_validate(summary) for summary in summaries]


@router.get(
    "/{summary_id}",
    response_model=AISummaryResponse,
    summary="Buscar resumo IA por ID",
    description="Retorna um resumo IA pelo UUID. Requer autenticação.",
    responses={
        200: {"description": "Resumo encontrado"},
        401: {"description": "Não autenticado"},
        404: {"description": "Resumo não encontrado"},
    },
)
def get_ai_summary(
    summary_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AISummaryResponse:
    ai_repo = AISummaryRepository(db)
    summary = ai_repo.get_by_id(summary_id)

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI summary with ID {summary_id} not found",
        )

    return AISummaryResponse.model_validate(summary)


@router.get(
    "/attendance/{attendance_id}",
    response_model=AISummaryResponse,
    summary="Resumo IA por atendimento",
    description="Retorna o resumo IA associado a um atendimento (um resumo por atendimento). Requer autenticação.",
    responses={
        200: {"description": "Resumo do atendimento"},
        401: {"description": "Não autenticado"},
        404: {"description": "Resumo para este atendimento não encontrado"},
    },
)
def get_ai_summary_by_attendance(
    attendance_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AISummaryResponse:
    ai_repo = AISummaryRepository(db)
    summary = ai_repo.get_by_attendance_id(attendance_id)

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI summary for attendance {attendance_id} not found",
        )

    return AISummaryResponse.model_validate(summary)


@router.get(
    "/client/{client_id}",
    response_model=List[AISummaryResponse],
    summary="Resumos IA por cliente",
    description="Lista todos os resumos IA dos atendimentos de um cliente, com paginação. Requer autenticação.",
    responses={
        200: {"description": "Lista de resumos do cliente"},
        401: {"description": "Não autenticado"},
    },
)
def get_ai_summaries_by_client(
    client_id: uuid.UUID,
    skip: int = Query(0, ge=0, description="Registros a pular"),
    limit: int = Query(100, ge=1, le=1000, description="Máximo de registros"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[AISummaryResponse]:
    ai_repo = AISummaryRepository(db)
    summaries = ai_repo.get_by_client_id(
        client_id=client_id,
        skip=skip,
        limit=limit,
    )
    return [AISummaryResponse.model_validate(summary) for summary in summaries]


@router.put(
    "/{summary_id}",
    response_model=AISummaryResponse,
    summary="Atualizar resumo IA",
    description="Atualização parcial do resumo (reprocessamento ou correção manual). Apenas os campos enviados são alterados. Requer autenticação.",
    responses={
        200: {"description": "Resumo atualizado"},
        401: {"description": "Não autenticado"},
        404: {"description": "Resumo não encontrado"},
        422: {"description": "Dados inválidos"},
    },
)
def update_ai_summary(
    summary_id: uuid.UUID,
    summary_data: AISummaryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AISummaryResponse:
    ai_repo = AISummaryRepository(db)
    summary = ai_repo.get_by_id(summary_id)

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI summary with ID {summary_id} not found",
        )

    updated_summary = ai_repo.update(summary, summary_data)
    return AISummaryResponse.model_validate(updated_summary)


@router.delete(
    "/{summary_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir resumo IA",
    description="Remove o resumo IA do sistema. Operação irreversível. Requer autenticação.",
    responses={
        204: {"description": "Resumo excluído"},
        401: {"description": "Não autenticado"},
        404: {"description": "Resumo não encontrado"},
    },
)
def delete_ai_summary(
    summary_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    ai_repo = AISummaryRepository(db)
    summary = ai_repo.get_by_id(summary_id)

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI summary with ID {summary_id} not found",
        )

    ai_repo.delete(summary)


