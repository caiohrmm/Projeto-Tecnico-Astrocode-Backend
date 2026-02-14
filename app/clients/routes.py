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
)
def create_client(
    client_data: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ClientWithClassification:
    """
    Create a new client with AI classification.

    The AI will analyze available information and provide:
    - Initial lead score (0-100)
    - Urgency level assessment
    - Interest type detection (if detectable)
    - Property type preferences (if detectable)
    - Recommended next actions

    Args:
        client_data: Client creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created client information with AI classification

    Raises:
        HTTPException: If client with same email already exists
    """
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
)
def list_clients(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    lead_source: LeadSource | None = Query(None, description="Filter by lead source"),
    search: str | None = Query(None, description="Search by name or phone"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[ClientResponse]:
    """
    List all clients with optional filtering and pagination.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        lead_source: Optional filter by lead source
        search: Optional search query to filter by name or phone
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of client information
    """
    repository = ClientRepository(db)
    clients = repository.get_all(skip=skip, limit=limit, lead_source=lead_source, search=search)
    return [ClientResponse.model_validate(client) for client in clients]


@router.get(
    "/{client_id}",
    response_model=ClientResponse,
    status_code=status.HTTP_200_OK,
)
def get_client(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ClientResponse:
    """
    Get client by ID.

    Args:
        client_id: Client UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Client information

    Raises:
        HTTPException: If client not found
    """
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
)
def update_client(
    client_id: uuid.UUID,
    client_data: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ClientResponse:
    """
    Update client information.

    Args:
        client_id: Client UUID
        client_data: Update data (only provided fields will be updated)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated client information

    Raises:
        HTTPException: If client not found or email already exists
    """
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
)
def delete_client(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """
    Delete a client.

    Args:
        client_id: Client UUID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If client not found
    """
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
)
def classify_lead(
    client_id: uuid.UUID,
    request: ClassifyLeadRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LeadClassificationResult:
    """
    Get current client classification based on AI analysis of all attendances.
    
    NOTE: This endpoint returns the current state derived from AI analysis.
    The system automatically detects and updates client profile whenever:
    - A new attendance is created
    - An attendance is updated
    - An attendance is completed
    
    The client's profile (interest, budget, urgency, lead_score) is continuously
    updated by the AI through the State Derivation Service, which analyzes all
    attendance summaries and consolidates signals.
    
    This endpoint simply returns the current derived state, not a new classification.

    Args:
        client_id: Client UUID
        request: Optional additional context (not used, kept for compatibility)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Current AI-derived classification result

    Raises:
        HTTPException: If client not found
    """
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
)
def apply_classification(
    client_id: uuid.UUID,
    classification: LeadClassificationResult,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ClientResponse:
    """
    Apply an AI classification to a client.

    This endpoint updates the client with the AI classification values.

    Args:
        client_id: Client UUID
        classification: AI classification to apply
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated client information

    Raises:
        HTTPException: If client not found
    """
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
)
def get_recommended_properties(
    client_id: uuid.UUID,
    limit: int = Query(5, ge=1, le=20, description="Maximum number of properties to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[PropertyResponse]:
    """
    Get recommended properties for a client based on their preferences.
    
    Uses client's current preferences:
    - current_interest_type (BUY/RENT)
    - current_property_type (HOUSE/APARTMENT/etc)
    - current_city_interest
    - current_budget_min and current_budget_max
    
    Args:
        client_id: Client UUID
        limit: Maximum number of properties to return (default: 5, max: 20)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of recommended properties matching client preferences
        
    Raises:
        HTTPException: If client not found
    """
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


