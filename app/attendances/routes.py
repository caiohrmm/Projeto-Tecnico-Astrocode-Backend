"""Attendance routes for CRUD operations."""

import logging
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.attendances.models import Attendance, AttendanceStatus
from app.attendances.repository import AttendanceRepository
from app.attendances.schemas import AttendanceCreate, AttendanceResponse, AttendanceUpdate
from app.db import get_db
from app.users.models import User
from app.users.repository import UserRepository

router = APIRouter(prefix="/attendances", tags=["attendances"])
logger = logging.getLogger(__name__)


def _validate_agent_is_corretor(agent_id: uuid.UUID, db: Session) -> None:
    """
    Validate that agent_id belongs to a user with 'corretor' role.

    Args:
        agent_id: UUID of the agent to validate
        db: Database session

    Raises:
        HTTPException: If agent_id is provided but user doesn't have 'corretor' role
    """
    user_repo = UserRepository(db)
    agent = user_repo.get_by_id(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {agent_id} not found",
        )

    # Check if user has 'corretor' role
    role_names = [role.name for role in agent.roles]
    if "corretor" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User {agent_id} does not have 'corretor' role. Only users with 'corretor' role can be assigned as agents.",
        )


@router.post(
    "/",
    response_model=AttendanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar ou acumular atendimento",
    description="""
Cria um novo ciclo de atendimento ou acumula conteúdo no ciclo ativo do cliente.

**Regra central – um ativo por cliente:** o cliente tem no máximo um atendimento com status ACTIVE. Se já existir um ativo, o conteúdo é acumulado nele e a resposta indica `cycle_action: CYCLE_UPDATED`. Só é criado um novo ciclo quando não há ativo (ex.: anterior fechado como COMPLETED/LOST/ABANDONED); nesse caso `cycle_action: NEW_CYCLE_CREATED` e opcionalmente `previous_cycle_id`.

**Agente:** `agent_id` é obrigatório e deve ser um usuário com role **corretor**; caso contrário retorna 400.

**Objetivo:** se não informado, é detectado automaticamente a partir do `raw_content`.

**Comportamentos automáticos:**
- Resumo (AI) é gerado para o atendimento.
- Se `updated_client_status` for enviado, o cliente é atualizado (status, interesse, tipo de imóvel).
- Se `scheduled_visit_at` for informado, uma visita pode ser criada (conforme regras do repositório).
- A IA pode devolver na resposta **sugestões** (não aplicadas automaticamente): `detected_visit`, `detected_loss`, `detected_sale`. Visita/perda/venda só são efetivadas após confirmação do usuário.

Requer autenticação.
    """.strip(),
    responses={
        201: {"description": "Atendimento criado ou ciclo atualizado"},
        400: {"description": "agent_id não é corretor ou dados inválidos"},
        401: {"description": "Não autenticado"},
        404: {"description": "Cliente, agente ou imóvel não encontrado"},
        422: {"description": "Payload inválido"},
    },
)
def create_attendance(
    attendance_data: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AttendanceResponse:
    # Validate agent_id must be a corretor
    _validate_agent_is_corretor(attendance_data.agent_id, db)

    attendance_repo = AttendanceRepository(db)
    
    # Track if there was an existing active attendance before creation
    existing_active = attendance_repo.get_active_attendance_by_client(attendance_data.client_id)
    existing_id = existing_active.id if existing_active else None
    
    attendance = attendance_repo.create(attendance_data)
    
    # Determine the action taken
    from app.attendances.schemas import CycleAction, DetectedVisitInfo
    
    if existing_active and existing_active.id != attendance.id:
        # New cycle created, previous one was closed
        cycle_action = CycleAction.NEW_CYCLE_CREATED
        previous_cycle_id = existing_active.id
    elif existing_active and existing_active.id == attendance.id:
        # Existing cycle was updated
        cycle_action = CycleAction.CYCLE_UPDATED
        previous_cycle_id = None
    else:
        # New cycle created (no previous active)
        cycle_action = CycleAction.NEW_CYCLE_CREATED
        previous_cycle_id = None
    
    # Detect visit intent from raw_content using AI
    detected_visit = None
    try:
        from app.ai.service import AISummaryService
        from datetime import datetime
        
        visit_info = AISummaryService.detect_visit_intent(
            raw_content=attendance.raw_content,
            client_id=attendance.client_id,
            property_id=attendance.property_id,
            agent_id=attendance.agent_id,
        )
        
        if visit_info and visit_info.get("detected"):
            detected_visit = DetectedVisitInfo(**visit_info)
            # ⚠️ IMPORTANT: Visit is NOT created automatically - user must confirm via frontend dialog
            logger.info(f"Visit intent detected (user confirmation required): {detected_visit.scheduled_at}")
    except Exception as e:
        # Log error but don't fail the request
        logger.warning(f"Error detecting visit intent: {e}", exc_info=True)
    
    # Detect loss intent from raw_content using AI
    # ⚠️ IMPORTANT: This is ONLY a suggestion. Attendance status remains ACTIVE until user confirms.
    detected_loss = None
    try:
        from app.ai.service import AISummaryService
        from app.attendances.schemas import DetectedLossInfo
        
        # ⚠️ PROTECTION: Only detect if attendance is still ACTIVE (not LOST, COMPLETED, or ABANDONED)
        # This prevents multiple detections and annoying popups
        if attendance.status.value == "ACTIVE":
            loss_info = AISummaryService.detect_loss_intent(
                raw_content=attendance.raw_content,
                client_id=attendance.client_id,
                property_id=attendance.property_id,
                agent_id=attendance.agent_id,
                attendance_status=attendance.status.value,  # Pass current status to skip if LOST
            )
            
            if loss_info and loss_info.get("detected"):
                detected_loss = DetectedLossInfo(**loss_info)
                logger.info(f"Loss intent detected (suggestion only): {detected_loss.loss_reason} at stage {detected_loss.loss_stage}. Attendance remains ACTIVE until user confirms.")
        else:
                logger.debug(f"Skipping loss detection: attendance status is {attendance.status.value} (not ACTIVE)")
    except Exception as e:
        # Log error but don't fail the request
        logger.warning(f"Error detecting loss intent: {e}", exc_info=True)
    
    # Detect sale intent from raw_content using AI
    # ⚠️ IMPORTANT: This is ONLY a suggestion. Attendance status remains ACTIVE until user confirms.
    detected_sale = None
    try:
        from app.ai.service import AISummaryService
        from app.attendances.schemas import DetectedSaleInfo
        
        # ⚠️ PROTECTION: Only detect if attendance is still ACTIVE (not COMPLETED, LOST, or ABANDONED)
        # This prevents multiple detections and annoying popups
        if attendance.status.value == "ACTIVE":
            # Usar imóvel do atendimento ou da visita vinculada (mais recente) para pré-preencher o modal de venda
            sale_property_id = attendance.property_id
            if not sale_property_id:
                from app.visits.repository import VisitRepository
                visit_repo = VisitRepository(db)
                recent_visit = visit_repo.get_most_recent_visit_with_property(attendance.id)
                if recent_visit:
                    sale_property_id = recent_visit.property_id
            sale_info = AISummaryService.detect_sale_intent(
                raw_content=attendance.raw_content,
                client_id=attendance.client_id,
                property_id=sale_property_id,
                agent_id=attendance.agent_id,
                attendance_status=attendance.status.value,  # Pass current status to skip if COMPLETED
            )
            
            if sale_info and sale_info.get("detected"):
                detected_sale = DetectedSaleInfo(**sale_info)
                logger.info(f"Sale intent detected (suggestion only): {detected_sale.sale_type} for {detected_sale.sale_value}. Attendance remains ACTIVE until user confirms.")
        else:
            logger.debug(f"Skipping sale detection: attendance status is {attendance.status.value} (not ACTIVE)")
    except Exception as e:
        # Log error but don't fail the request
        logger.warning(f"Error detecting sale intent: {e}", exc_info=True)
    
    # Create response with cycle action info, detected visit, detected loss, and detected sale
    # Use model_validate and then add cycle action fields using model_copy
    response = AttendanceResponse.model_validate(attendance)
    response = response.model_copy(update={
        'cycle_action': cycle_action,
        'previous_cycle_id': previous_cycle_id,
        'detected_visit': detected_visit,
        'detected_loss': detected_loss,
        'detected_sale': detected_sale,
    })
    
    return response


@router.get(
    "/",
    response_model=List[AttendanceResponse],
    summary="Listar atendimentos",
    description="""
Lista atendimentos com paginação e filtros opcionais.

**Filtros:** client_id, agent_id, property_id, status (ACTIVE, COMPLETED, LOST, ABANDONED).  
**available_for_visit:** quando true, retorna apenas atendimentos que podem receber uma nova visita (sem visita pendente).

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Lista de atendimentos"},
        401: {"description": "Não autenticado"},
    },
)
def list_attendances(
    skip: int = Query(0, ge=0, description="Registros a pular (paginação)"),
    limit: int = Query(100, ge=1, le=1000, description="Máximo de registros a retornar"),
    client_id: uuid.UUID | None = Query(None, description="Filtrar por cliente"),
    agent_id: uuid.UUID | None = Query(None, description="Filtrar por agente"),
    property_id: uuid.UUID | None = Query(None, description="Filtrar por imóvel"),
    status: AttendanceStatus | None = Query(None, description="Filtrar por status"),
    available_for_visit: bool = Query(False, description="Apenas atendimentos que podem receber nova visita"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[AttendanceResponse]:
    attendance_repo = AttendanceRepository(db)
    attendances = attendance_repo.get_all(
        skip=skip,
        limit=limit,
        client_id=client_id,
        agent_id=agent_id,
        property_id=property_id,
        status=status,
        available_for_visit=available_for_visit,
    )
    
    # Serialize attendances with error handling
    result = []
    for attendance in attendances:
        try:
            result.append(AttendanceResponse.model_validate(attendance))
        except Exception as e:
            logger.error(f"Error serializing attendance {attendance.id}: {e}", exc_info=True)
            # Continue with other attendances even if one fails
            continue
    
    return result


@router.get(
    "/active/client/{client_id}",
    response_model=AttendanceResponse,
    summary="Atendimento ativo do cliente",
    description="""
Retorna o atendimento com status ACTIVE do cliente, se existir.

**Regra:** existe no máximo um atendimento ACTIVE por cliente. Útil para saber se já há ciclo em andamento antes de criar outro ou para acumular conteúdo no ciclo atual.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Atendimento ativo encontrado"},
        401: {"description": "Não autenticado"},
        404: {"description": "Nenhum atendimento ativo para o cliente"},
    },
)
def get_active_attendance_by_client(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AttendanceResponse:
    attendance_repo = AttendanceRepository(db)
    attendance = attendance_repo.get_active_attendance_by_client(client_id)

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active attendance found for client {client_id}",
        )

    return AttendanceResponse.model_validate(attendance)


@router.get(
    "/{attendance_id}",
    response_model=AttendanceResponse,
    summary="Buscar atendimento por ID",
    description="Retorna um atendimento pelo UUID. Inclui ciclo, resumo IA, status e (quando aplicável) sugestões de visita/perda/venda detectadas pela IA.",
    responses={
        200: {"description": "Atendimento encontrado"},
        401: {"description": "Não autenticado"},
        404: {"description": "Atendimento não encontrado"},
    },
)
def get_attendance(
    attendance_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AttendanceResponse:
    attendance_repo = AttendanceRepository(db)
    attendance = attendance_repo.get_by_id(attendance_id)

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance with ID {attendance_id} not found",
        )

    return AttendanceResponse.model_validate(attendance)


@router.put(
    "/{attendance_id}",
    response_model=AttendanceResponse,
    summary="Atualizar atendimento",
    description="""
Atualização parcial: apenas os campos enviados são alterados.

**Regras:**
- **agent_id:** se informado, deve ser usuário com role corretor (400 caso contrário).
- **Objetivo:** alterar o objective em um atendimento ACTIVE não fecha nem recria ciclo automaticamente; controle é manual.
- **Status → COMPLETED:** ao marcar como COMPLETED, o resumo (AI) pode ser regenerado.
- **raw_content / campos de IA:** ao atualizar conteúdo ou campos usados pela IA em atendimento COMPLETED, o resumo pode ser regenerado.
- **updated_client_status:** atualiza status, tipo de interesse e tipo de imóvel do cliente.
- **scheduled_visit_at:** se informado e ainda não houver, pode criar visita (conforme repositório).

**Detecção na atualização:** se `raw_content` for enviado, a IA pode devolver na resposta sugestões `detected_visit`, `detected_loss`, `detected_sale` (apenas quando status ainda é ACTIVE). Nada é aplicado automaticamente; usuário confirma no front.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Atendimento atualizado"},
        400: {"description": "agent_id não é corretor"},
        401: {"description": "Não autenticado"},
        404: {"description": "Atendimento não encontrado"},
        422: {"description": "Payload inválido"},
    },
)
def update_attendance(
    attendance_id: uuid.UUID,
    attendance_data: AttendanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AttendanceResponse:
    # Validate agent_id if being updated
    if attendance_data.agent_id is not None:
        _validate_agent_is_corretor(attendance_data.agent_id, db)

    attendance_repo = AttendanceRepository(db)
    attendance = attendance_repo.get_by_id(attendance_id)

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance with ID {attendance_id} not found",
        )

    updated_attendance = attendance_repo.update(attendance, attendance_data)
    
    # Detect visit intent if raw_content was updated
    detected_visit = None
    if attendance_data.raw_content is not None:
        try:
            from app.ai.service import AISummaryService
            from app.attendances.schemas import DetectedVisitInfo
            from datetime import datetime
            
            visit_info = AISummaryService.detect_visit_intent(
                raw_content=updated_attendance.raw_content,
                client_id=updated_attendance.client_id,
                property_id=updated_attendance.property_id,
                agent_id=updated_attendance.agent_id,
            )
            
            if visit_info and visit_info.get("detected"):
                detected_visit = DetectedVisitInfo(**visit_info)
                # ⚠️ IMPORTANT: Visit is NOT created automatically - user must confirm via frontend dialog
                logger.info(f"Visit intent detected (user confirmation required): {detected_visit.scheduled_at}")
        except Exception as e:
            # Log error but don't fail the request
            logger.warning(f"Error detecting visit intent: {e}", exc_info=True)
    
    # Detect loss intent if raw_content was updated
    # ⚠️ IMPORTANT: This is ONLY a suggestion. Attendance status remains ACTIVE until user confirms.
    detected_loss = None
    if attendance_data.raw_content is not None:
        try:
            from app.ai.service import AISummaryService
            from app.attendances.schemas import DetectedLossInfo
            
            # ⚠️ PROTECTION: Only detect if attendance is still ACTIVE (not LOST, COMPLETED, or ABANDONED)
            # This prevents multiple detections and annoying popups
            if updated_attendance.status.value == "ACTIVE":
                loss_info = AISummaryService.detect_loss_intent(
                    raw_content=updated_attendance.raw_content,
                    client_id=updated_attendance.client_id,
                    property_id=updated_attendance.property_id,
                    agent_id=updated_attendance.agent_id,
                    attendance_status=updated_attendance.status.value,  # Pass current status to skip if LOST
                )
                
                if loss_info and loss_info.get("detected"):
                    detected_loss = DetectedLossInfo(**loss_info)
                    logger.info(f"Loss intent detected (suggestion only): {detected_loss.loss_reason} at stage {detected_loss.loss_stage}. Attendance remains ACTIVE until user confirms.")
            else:
                logger.debug(f"Skipping loss detection: attendance status is {updated_attendance.status.value} (not ACTIVE)")
        except Exception as e:
            # Log error but don't fail the request
            logger.warning(f"Error detecting loss intent: {e}", exc_info=True)
    
    # Detect sale intent if raw_content was updated
    # ⚠️ IMPORTANT: This is ONLY a suggestion. Attendance status remains ACTIVE until user confirms.
    detected_sale = None
    if attendance_data.raw_content is not None:
        try:
            from app.ai.service import AISummaryService
            from app.attendances.schemas import DetectedSaleInfo
            
            # ⚠️ PROTECTION: Only detect if attendance is still ACTIVE (not COMPLETED, LOST, or ABANDONED)
            # This prevents multiple detections and annoying popups
            if updated_attendance.status.value == "ACTIVE":
                # Usar imóvel do atendimento ou da visita vinculada (mais recente) para pré-preencher o modal de venda
                sale_property_id = updated_attendance.property_id
                if not sale_property_id:
                    from app.visits.repository import VisitRepository
                    visit_repo = VisitRepository(db)
                    recent_visit = visit_repo.get_most_recent_visit_with_property(updated_attendance.id)
                    if recent_visit:
                        sale_property_id = recent_visit.property_id
                sale_info = AISummaryService.detect_sale_intent(
                    raw_content=updated_attendance.raw_content,
                    client_id=updated_attendance.client_id,
                    property_id=sale_property_id,
                    agent_id=updated_attendance.agent_id,
                    attendance_status=updated_attendance.status.value,  # Pass current status to skip if COMPLETED
                )
                
                if sale_info and sale_info.get("detected"):
                    detected_sale = DetectedSaleInfo(**sale_info)
                    logger.info(f"Sale intent detected (suggestion only): {detected_sale.sale_type} for {detected_sale.sale_value}. Attendance remains ACTIVE until user confirms.")
            else:
                logger.debug(f"Skipping sale detection: attendance status is {updated_attendance.status.value} (not ACTIVE)")
        except Exception as e:
            # Log error but don't fail the request
            logger.warning(f"Error detecting sale intent: {e}", exc_info=True)
    
    response = AttendanceResponse.model_validate(updated_attendance)
    update_dict = {}
    if detected_visit:
        update_dict['detected_visit'] = detected_visit
    if detected_loss:
        update_dict['detected_loss'] = detected_loss
    if detected_sale:
        update_dict['detected_sale'] = detected_sale
    if update_dict:
        response = response.model_copy(update=update_dict)
    
    return response


@router.delete(
    "/{attendance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir atendimento",
    description="Remove o atendimento do sistema. Operação irreversível. Requer autenticação.",
    responses={
        204: {"description": "Atendimento excluído"},
        401: {"description": "Não autenticado"},
        404: {"description": "Atendimento não encontrado"},
    },
)
def delete_attendance(
    attendance_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    attendance_repo = AttendanceRepository(db)
    attendance = attendance_repo.get_by_id(attendance_id)

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance with ID {attendance_id} not found",
        )

    attendance_repo.delete(attendance)

