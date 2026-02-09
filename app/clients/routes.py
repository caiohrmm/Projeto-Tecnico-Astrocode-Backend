"""Client routes for CRUD operations."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.ai.lead_classifier import lead_classifier, LeadClassification
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
from app.users.models import User
from app.users.repository import UserRepository

router = APIRouter(prefix="/clients", tags=["clients"])


def _validate_agent_is_corretor(assigned_agent_id: uuid.UUID | None, db: Session) -> None:
    """
    Validate that assigned_agent_id belongs to a user with 'corretor' role.

    Args:
        assigned_agent_id: UUID of the agent to validate
        db: Database session

    Raises:
        HTTPException: If agent_id is provided but user doesn't have 'corretor' role
    """
    if assigned_agent_id is None:
        return  # No validation needed if no agent is assigned

    user_repo = UserRepository(db)
    agent = user_repo.get_by_id(assigned_agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {assigned_agent_id} not found",
        )

    # Check if user has 'corretor' role
    role_names = [role.name for role in agent.roles]
    if "corretor" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User {assigned_agent_id} does not have 'corretor' role. Only users with 'corretor' role can be assigned as agents.",
        )


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

    # Validate assigned_agent_id if provided
    _validate_agent_is_corretor(client_data.assigned_agent_id, db)

    # AI Classification (if enabled and not already provided)
    classification: LeadClassification | None = None
    if client_data.use_ai_classification:
        classification = lead_classifier.classify_lead(
            name=client_data.name,
            phone=client_data.phone,
            email=client_data.email,
            lead_source=client_data.lead_source.value,
            initial_message=client_data.initial_message,
            notes=client_data.summary_notes,
        )
        
        # Apply AI classification to client data if not already set
        if client_data.current_lead_score is None:
            client_data.current_lead_score = classification.lead_score
        
        if client_data.current_urgency_level is None:
            client_data.current_urgency_level = classification.urgency_level
        
        if client_data.current_interest_type is None and classification.interest_type:
            client_data.current_interest_type = classification.interest_type
        
        if client_data.current_property_type is None and classification.property_type:
            client_data.current_property_type = classification.property_type
        
        if client_data.current_status is None:
            client_data.current_status = classification.suggested_status

    # Create client
    client = repository.create(client_data)
    
    # Build response with classification
    response_data = ClientResponse.model_validate(client).model_dump()
    
    if classification:
        response_data["ai_classification"] = LeadClassificationResult(
            lead_score=classification.lead_score,
            urgency_level=classification.urgency_level,
            interest_type=classification.interest_type,
            property_type=classification.property_type,
            suggested_status=classification.suggested_status,
            classification_reason=classification.classification_reason,
            key_indicators=classification.key_indicators,
            recommended_actions=classification.recommended_actions,
            confidence=classification.confidence,
        )
    else:
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[ClientResponse]:
    """
    List all clients with optional filtering and pagination.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        lead_source: Optional filter by lead source
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of client information
    """
    repository = ClientRepository(db)
    clients = repository.get_all(skip=skip, limit=limit, lead_source=lead_source)
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

    # Validate assigned_agent_id if being updated
    if client_data.assigned_agent_id is not None:
        _validate_agent_is_corretor(client_data.assigned_agent_id, db)

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
    Classify or reclassify a lead using AI.

    This endpoint analyzes the client's information and interaction history
    to provide an updated classification with:
    - Lead score
    - Urgency level
    - Interest/property type detection
    - Recommendations

    Args:
        client_id: Client UUID
        request: Optional additional context for classification
        db: Database session
        current_user: Current authenticated user

    Returns:
        AI classification result

    Raises:
        HTTPException: If client not found
    """
    from app.attendances.repository import AttendanceRepository
    from datetime import datetime
    
    repository = ClientRepository(db)
    client = repository.get_by_id(client_id)
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    # Get attendance history
    attendance_repo = AttendanceRepository(db)
    attendances = attendance_repo.get_by_client(client_id)
    
    # Get last attendance summary
    last_summary = None
    if attendances:
        last_attendance = attendances[0]  # Most recent
        if last_attendance.ai_summary:
            last_summary = last_attendance.ai_summary.summary
    
    # Calculate days since first contact
    days_since_first = 0
    if client.first_contact_at:
        days_since_first = (datetime.utcnow() - client.first_contact_at).days
    
    # Classify using AI
    classification = lead_classifier.reclassify_lead(
        name=client.name,
        phone=client.phone,
        email=client.email,
        lead_source=client.lead_source.value,
        current_status=client.current_status.value if client.current_status else None,
        attendances_count=len(attendances),
        visits_count=0,  # TODO: Get from visits repo
        days_since_first_contact=days_since_first,
        last_attendance_summary=last_summary,
        budget_min=float(client.current_budget_min) if client.current_budget_min else None,
        budget_max=float(client.current_budget_max) if client.current_budget_max else None,
        city_interest=client.current_city_interest,
    )
    
    return LeadClassificationResult(
        lead_score=classification.lead_score,
        urgency_level=classification.urgency_level,
        interest_type=classification.interest_type,
        property_type=classification.property_type,
        suggested_status=classification.suggested_status,
        classification_reason=classification.classification_reason,
        key_indicators=classification.key_indicators,
        recommended_actions=classification.recommended_actions,
        confidence=classification.confidence,
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
    
    # Apply update
    updated_client = repository.update(client, update_data)
    
    return ClientResponse.model_validate(updated_client)


