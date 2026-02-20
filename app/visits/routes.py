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
from app.attendances.schemas import AttendanceUpdate as AttendanceUpdateSchema

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


@router.post(
    "/",
    response_model=VisitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar visita",
    description="""
Cria uma nova visita ao imóvel.

**Regras:**
- **Corretor:** `broker_id` é obrigatório e deve ser usuário com role **corretor** (400/404 se não for).
- **Vínculo com atendimento:** se `attendance_id` for informado, o atendimento deve existir, ter status **ACTIVE** e **não** possuir visita pendente (agendada ou em andamento). Caso já exista visita pendente para esse atendimento, retorna 400.
- **Sincronização:** ao criar visita vinculada a um atendimento, o campo `scheduled_visit_at` do atendimento é atualizado com a data da visita.

Requer autenticação.
    """.strip(),
    responses={
        201: {"description": "Visita criada"},
        400: {"description": "broker_id não é corretor, atendimento não ACTIVE ou já possui visita pendente"},
        401: {"description": "Não autenticado"},
        404: {"description": "Atendimento não encontrado"},
        422: {"description": "Dados inválidos"},
    },
)
def create_visit(
    visit_data: VisitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> VisitResponse:
    # Validate broker_id must be a corretor
    _validate_broker_is_corretor(visit_data.broker_id, db)

    attendance_repo = AttendanceRepository(db)
    visit_repo = VisitRepository(db)

    # If visit is linked to an attendance, ensure attendance exists, is ACTIVE, and has no pending visit
    if visit_data.attendance_id is not None:
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

        if visit_repo.has_pending_visit(visit_data.attendance_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este atendimento já possui uma visita agendada ou em andamento. Conclua ou cancele a visita antes de criar outra.",
            )

    visit = visit_repo.create(visit_data)

    # Sync scheduled_visit_at on attendance so IA/resumo always sees the visit date
    if visit.attendance_id and visit.scheduled_at:
        attendance = attendance_repo.get_by_id(visit.attendance_id)
        if attendance:
            attendance_repo.update(attendance, AttendanceUpdateSchema(scheduled_visit_at=visit.scheduled_at))

    return VisitResponse.model_validate(visit)


@router.get(
    "/",
    response_model=List[VisitResponse],
    summary="Listar visitas",
    description="""
Lista visitas com paginação e filtros opcionais.

**Filtros:** client_id, broker_id, property_id, attendance_id, status (SCHEDULED, CONFIRMED, IN_PROGRESS, COMPLETED, CANCELLED, NO_SHOW), scheduled_from, scheduled_to.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Lista de visitas"},
        401: {"description": "Não autenticado"},
    },
)
def list_visits(
    skip: int = Query(0, ge=0, description="Registros a pular (paginação)"),
    limit: int = Query(100, ge=1, le=1000, description="Máximo de registros a retornar"),
    client_id: uuid.UUID | None = Query(None, description="Filtrar por cliente"),
    broker_id: uuid.UUID | None = Query(None, description="Filtrar por corretor"),
    property_id: uuid.UUID | None = Query(None, description="Filtrar por imóvel"),
    attendance_id: uuid.UUID | None = Query(None, description="Filtrar por atendimento"),
    status: VisitStatus | None = Query(None, description="Filtrar por status"),
    scheduled_from: datetime | None = Query(None, description="Data agendada a partir de"),
    scheduled_to: datetime | None = Query(None, description="Data agendada até"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[VisitResponse]:
    visit_repo = VisitRepository(db)
    visits = visit_repo.get_all(
        skip=skip,
        limit=limit,
        client_id=client_id,
        broker_id=broker_id,
        property_id=property_id,
        attendance_id=attendance_id,
        status=status,
        scheduled_from=scheduled_from,
        scheduled_to=scheduled_to,
    )
    return [VisitResponse.model_validate(visit) for visit in visits]


@router.get(
    "/{visit_id}",
    response_model=VisitResponse,
    summary="Buscar visita por ID",
    description="Retorna uma visita pelo UUID. Inclui cliente, corretor, imóvel, atendimento (se vinculado), data agendada, status e notas.",
    responses={
        200: {"description": "Visita encontrada"},
        401: {"description": "Não autenticado"},
        404: {"description": "Visita não encontrada"},
    },
)
def get_visit(
    visit_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> VisitResponse:
    visit_repo = VisitRepository(db)
    visit = visit_repo.get_by_id(visit_id)

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visit with ID {visit_id} not found",
        )

    return VisitResponse.model_validate(visit)


@router.put(
    "/{visit_id}",
    response_model=VisitResponse,
    summary="Atualizar visita",
    description="""
Atualização parcial: apenas os campos enviados são considerados.

**Visita vinculada a atendimento (attendance_id preenchido):** somente **scheduled_at** e **status** podem ser alterados (reagendamento). Demais campos são ignorados. O campo `scheduled_visit_at` do atendimento é mantido em sincronia quando `scheduled_at` da visita é atualizado.

**Visita não vinculada:** todos os campos podem ser atualizados. Ao alterar `broker_id`, o usuário deve ser corretor. Ao vincular a um atendimento (`attendance_id`), o atendimento deve existir, estar ACTIVE e não possuir visita pendente.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Visita atualizada"},
        400: {"description": "broker_id não é corretor, atendimento não ACTIVE ou já possui visita pendente"},
        401: {"description": "Não autenticado"},
        404: {"description": "Visita ou atendimento não encontrado"},
        422: {"description": "Dados inválidos"},
    },
)
def update_visit(
    visit_id: uuid.UUID,
    visit_data: VisitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> VisitResponse:
    visit_repo = VisitRepository(db)
    visit = visit_repo.get_by_id(visit_id)

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visit with ID {visit_id} not found",
        )

    attendance_repo = AttendanceRepository(db)

    # Visit linked to attendance: only allow scheduled_at and status (reagendamento)
    if visit.attendance_id is not None:
        allowed = {}
        if visit_data.scheduled_at is not None:
            allowed["scheduled_at"] = visit_data.scheduled_at
        if visit_data.status is not None:
            allowed["status"] = visit_data.status
        visit_data = VisitUpdate(**allowed)
    else:
        if visit_data.broker_id is not None:
            _validate_broker_is_corretor(visit_data.broker_id, db)
        # When not linked, do not allow changing attendance_id to one that has pending visit
        if visit_data.attendance_id is not None:
            att = attendance_repo.get_by_id(visit_data.attendance_id)
            if not att:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Attendance with ID {visit_data.attendance_id} not found",
                )
            if att.status != AttendanceStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Só é permitido vincular visitas a atendimentos com status ACTIVE (Ativo).",
                )
            if visit_repo.has_pending_visit(visit_data.attendance_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Este atendimento já possui uma visita agendada ou em andamento.",
                )

    updated_visit = visit_repo.update(visit, visit_data)

    # Sync attendance.scheduled_visit_at when visit linked and scheduled_at was updated
    if updated_visit.attendance_id and updated_visit.scheduled_at:
        attendance = attendance_repo.get_by_id(updated_visit.attendance_id)
        if attendance:
            attendance_repo.update(attendance, AttendanceUpdateSchema(scheduled_visit_at=updated_visit.scheduled_at))

    return VisitResponse.model_validate(updated_visit)


@router.delete(
    "/{visit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir visita",
    description="Remove a visita do sistema. Operação irreversível. Requer autenticação.",
    responses={
        204: {"description": "Visita excluída"},
        401: {"description": "Não autenticado"},
        404: {"description": "Visita não encontrada"},
    },
)
def delete_visit(
    visit_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    visit_repo = VisitRepository(db)
    visit = visit_repo.get_by_id(visit_id)

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visit with ID {visit_id} not found",
        )

    visit_repo.delete(visit)

