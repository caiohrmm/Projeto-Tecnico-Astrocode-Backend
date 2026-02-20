"""Client routes for CRUD operations."""

import uuid
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

# Lead Classifier removed - system now detects changes through attendances and AI analysis
from app.auth.dependencies import get_current_active_user
from app.clients.models import Client, LeadSource
from app.clients.repository import ClientRepository
from app.clients.schemas import (
    ClassifyLeadRequest,
    ClientCreate,
    ClientResponse,
    ClientUpdate,
    ClientWithClassification,
    LeadClassificationResult,
)
from app.db import get_db
from app.properties.repository import PropertyRepository
from app.properties.schemas import PropertyResponse
from app.users.models import User

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post(
    "/",
    response_model=ClientWithClassification,
    status_code=status.HTTP_201_CREATED,
    summary="Criar cliente",
    description="""
Cria um novo cliente no CRM.

**Regras de negócio:**
- **E-mail único:** se informado, não pode existir outro cliente com o mesmo e-mail.
- **Valores iniciais:** status padrão `NEW_LEAD`, urgência `MEDIUM`, lead score `30` (ajustados pela IA quando houver primeiro atendimento).
- **Perfil do cliente:** interesse, orçamento, lead score etc. passam a ser atualizados **automaticamente pela IA** a partir dos atendimentos (ciclo ativo). Não é feita classificação inicial na criação; o primeiro atendimento dispara a análise.

Requer autenticação.
    """.strip(),
    responses={
        201: {"description": "Cliente criado"},
        400: {"description": "E-mail já cadastrado"},
        401: {"description": "Não autenticado"},
        422: {"description": "Dados inválidos (ex.: orçamento máx. < mín.)"},
    },
)
def create_client(
    client_data: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ClientWithClassification:
    repository = ClientRepository(db)

    # Check if client with same email already exists (only if email is provided)
    if client_data.email:
        existing_client = repository.get_by_email(client_data.email)
        if existing_client:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client with this email already exists",
            )

    # NOTE: Lead Classifier removed - the system now detects and updates client profile
    # automatically through attendances. When a new attendance is created, the AI analyzes
    # the conversation and updates the client's profile (interest, budget, urgency, lead_score)
    # through the State Derivation Service.
    #
    # The system is always attentive to changes:
    # - New attendance → AI analyzes → Updates client profile
    # - Attendance update → AI re-analyzes → Updates client profile
    # - All changes are detected automatically through AI summaries and state derivation
    
    # Set default values for new clients (will be updated by AI when first attendance is created)
    from app.clients.models import ClientStatus, UrgencyLevel
    if client_data.current_status is None:
        client_data.current_status = ClientStatus.NEW_LEAD
    if client_data.current_urgency_level is None:
        client_data.current_urgency_level = UrgencyLevel.MEDIUM
    if client_data.current_lead_score is None:
        # Default initial score - will be updated by AI when first attendance is analyzed
        client_data.current_lead_score = 30

    # Create client
    client = repository.create(client_data)
    
    # Build response (no initial classification - will happen when first attendance is created)
    response_data = ClientResponse.model_validate(client).model_dump()
    response_data["ai_classification"] = None
    
    return ClientWithClassification(**response_data)


@router.get(
    "/",
    response_model=List[ClientResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar clientes",
    description="""
Lista clientes com paginação e filtros opcionais.

**Parâmetros:**
- **skip / limit:** paginação (limit máx. 1000).
- **lead_source:** filtrar por origem do lead (ex.: WHATSAPP, WEBSITE).
- **search:** busca por nome ou telefone (parcial).

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Lista de clientes"},
        401: {"description": "Não autenticado"},
    },
)
def list_clients(
    skip: int = Query(0, ge=0, description="Registros a pular (paginação)"),
    limit: int = Query(100, ge=1, le=1000, description="Máximo de registros a retornar"),
    lead_source: LeadSource | None = Query(None, description="Filtrar por origem do lead"),
    search: str | None = Query(None, description="Buscar por nome ou telefone"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[ClientResponse]:
    repository = ClientRepository(db)
    clients = repository.get_all(skip=skip, limit=limit, lead_source=lead_source, search=search)
    return [ClientResponse.model_validate(client) for client in clients]


@router.get(
    "/{client_id}",
    response_model=ClientResponse,
    status_code=status.HTTP_200_OK,
    summary="Buscar cliente por ID",
    description="Retorna um cliente pelo UUID. Inclui perfil derivado (status, lead score, urgência, interesse, orçamento) e metadados de derivação pela IA (última derivação, quantidade de atendimentos considerados).",
    responses={
        200: {"description": "Cliente encontrado"},
        401: {"description": "Não autenticado"},
        404: {"description": "Cliente não encontrado"},
    },
)
def get_client(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ClientResponse:
    repository = ClientRepository(db)
    client = repository.get_by_id(client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    return ClientResponse.model_validate(client)


@router.put(
    "/{client_id}",
    response_model=ClientResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualizar cliente",
    description="""
Atualização parcial: apenas os campos enviados são alterados.

**Regras:**
- **E-mail:** ao alterar, não pode coincidir com o de outro cliente.
- **Lead score:** controlado pela IA; atualizações manuais podem ser ignoradas (o sistema prioriza a derivação a partir dos atendimentos).
- **Orçamento:** `current_budget_max` deve ser ≥ `current_budget_min`.
    """.strip(),
    responses={
        200: {"description": "Cliente atualizado"},
        400: {"description": "E-mail já usado por outro cliente"},
        401: {"description": "Não autenticado"},
        404: {"description": "Cliente não encontrado"},
        422: {"description": "Dados inválidos (ex.: orçamento)"},
    },
)
def update_client(
    client_id: uuid.UUID,
    client_data: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ClientResponse:
    repository = ClientRepository(db)
    client = repository.get_by_id(client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    # Check if email is being updated and if it conflicts with existing client
    if client_data.email and client_data.email != client.email:
        existing_client = repository.get_by_email(client_data.email)
        if existing_client:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client with this email already exists",
            )

    updated_client = repository.update(client, client_data)
    return ClientResponse.model_validate(updated_client)


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir cliente",
    description="Remove o cliente do sistema. Operação irreversível. Dados relacionados (atendimentos, visitas, vendas, perdas) podem ser tratados conforme regras do repositório.",
    responses={
        204: {"description": "Cliente excluído"},
        401: {"description": "Não autenticado"},
        404: {"description": "Cliente não encontrado"},
    },
)
def delete_client(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    repository = ClientRepository(db)
    client = repository.get_by_id(client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    repository.delete(client)


@router.post(
    "/{client_id}/classify",
    response_model=LeadClassificationResult,
    status_code=status.HTTP_200_OK,
    summary="Classificação atual do cliente (IA)",
    description="""
Retorna o **estado atual** do cliente já derivado pela IA (não executa nova análise).

**Regra importante:** o perfil do cliente (lead score, urgência, interesse, status) é atualizado **automaticamente** pelo **State Derivation Service** a partir **apenas do ciclo de atendimento ACTIVE**. Sempre que há novo atendimento ou atualização de conversa, a IA analisa e consolida os sinais.

Este endpoint apenas devolve o estado já calculado: score, urgência, tipo de interesse, tipo de imóvel, status sugerido, motivo, indicadores e ações recomendadas.
    """.strip(),
    responses={
        200: {"description": "Classificação atual derivada da IA"},
        401: {"description": "Não autenticado"},
        404: {"description": "Cliente não encontrado"},
    },
)
def classify_lead(
    client_id: uuid.UUID,
    request: ClassifyLeadRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LeadClassificationResult:
    repository = ClientRepository(db)
    client = repository.get_by_id(client_id)
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    # Return current client state (already derived by AI from attendances)
    # The system is always attentive - any change in attendances automatically
    # triggers AI analysis and client profile update
    from app.clients.state_derivation_service import ClientStateDerivationService
    
    # Get current derived state from ACTIVE cycle only
    # ⚠️ IMPORTANT: Client profile reflects ONLY the current ACTIVE cycle
    derivation_result = ClientStateDerivationService.derive_client_state(
        client_id=client_id,
        db=db,
        respect_human_values=True,
        only_active_attendances=True,  # ⚠️ ONLY consider ACTIVE attendance cycle
        max_cycles=None,
        use_cluster_logic=True,
    )
    
    # Build response from current client state
    return LeadClassificationResult(
        lead_score=client.current_lead_score or 30,
        urgency_level=client.current_urgency_level or "MEDIUM",
        interest_type=client.current_interest_type.value if client.current_interest_type else None,
        property_type=client.current_property_type.value if client.current_property_type else None,
        suggested_status=client.current_status.value if client.current_status else "NEW_LEAD",
        classification_reason="Estado atual derivado automaticamente pela IA através das análises de atendimentos",
        key_indicators=[
            f"Atendimentos analisados: {derivation_result.get('signals_count', 0)}",
            f"Última atualização: {client.last_state_derivation_at.strftime('%d/%m/%Y %H:%M') if client.last_state_derivation_at else 'Nunca'}",
        ],
        recommended_actions=[
            "O sistema detecta automaticamente mudanças através dos atendimentos",
            "Cada nova conversa é analisada pela IA e atualiza o perfil do cliente",
        ],
        confidence=0.9,  # High confidence as it's derived from actual interactions
    )


@router.post(
    "/{client_id}/apply-classification",
    response_model=ClientResponse,
    status_code=status.HTTP_200_OK,
    summary="Aplicar classificação ao cliente",
    description="""
Aplica ao cliente os valores de uma classificação (ex.: retornada por **classify** ou por sugestões da IA).

**Atualiza:** lead score, urgência, tipo de interesse e tipo de imóvel. O repositório aceita atualização de lead score vinda desta rota (`allow_ai_lead_score_update=True`). Útil para aplicar sugestões da IA ou correções manuais aprovadas.
    """.strip(),
    responses={
        200: {"description": "Cliente atualizado com a classificação"},
        401: {"description": "Não autenticado"},
        404: {"description": "Cliente não encontrado"},
        422: {"description": "Payload de classificação inválido"},
    },
)
def apply_classification(
    client_id: uuid.UUID,
    classification: LeadClassificationResult,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ClientResponse:
    from app.clients.schemas import ClientUpdate
    
    repository = ClientRepository(db)
    client = repository.get_by_id(client_id)
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    # Build update data
    update_data = ClientUpdate(
        current_lead_score=classification.lead_score,
        current_urgency_level=classification.urgency_level,
    )
    
    if classification.interest_type:
        update_data.current_interest_type = classification.interest_type
    
    if classification.property_type:
        update_data.current_property_type = classification.property_type
    
    # Apply update - allow AI-driven lead_score updates from classification
    updated_client = repository.update(client, update_data, allow_ai_lead_score_update=True)
    
    return ClientResponse.model_validate(updated_client)


@router.get(
    "/{client_id}/recommended-properties",
    response_model=List[PropertyResponse],
    status_code=status.HTTP_200_OK,
    summary="Imóveis recomendados para o cliente",
    description="""
Lista imóveis que batem com o perfil atual do cliente.

**Critérios (do cliente):** tipo de interesse (compra/aluguel), tipo de imóvel, cidade de interesse, faixa de orçamento (mín./máx.). Se **nenhum** desses estiver preenchido, retorna lista vazia. O limite é configurável (padrão 5, máx. 20).
    """.strip(),
    responses={
        200: {"description": "Lista de imóveis recomendados (pode ser vazia)"},
        401: {"description": "Não autenticado"},
        404: {"description": "Cliente não encontrado"},
    },
)
def get_recommended_properties(
    client_id: uuid.UUID,
    limit: int = Query(5, ge=1, le=20, description="Máximo de imóveis a retornar (1–20)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[PropertyResponse]:
    client_repo = ClientRepository(db)
    client = client_repo.get_by_id(client_id)
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    # Get client preferences
    interest_type = client.current_interest_type.value if client.current_interest_type else None
    property_type = client.current_property_type
    city = client.current_city_interest
    budget_min = float(client.current_budget_min) if client.current_budget_min else None
    budget_max = float(client.current_budget_max) if client.current_budget_max else None
    
    import logging
    logger = logging.getLogger(__name__)
    
    # If no preferences set, return empty list
    if not any([interest_type, property_type, city, budget_min, budget_max]):
        return []
    
    # Find recommended properties
    property_repo = PropertyRepository(db)
    properties = property_repo.find_recommended_properties(
        interest_type=interest_type,
        property_type=property_type,
        city=city,
        budget_min=budget_min,
        budget_max=budget_max,
        limit=limit,
    )
    
    return [PropertyResponse.model_validate(prop) for prop in properties]


