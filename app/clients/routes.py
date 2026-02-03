"""Client routes for CRUD operations."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.clients.models import Client, LeadSource
from app.clients.repository import ClientRepository
from app.clients.schemas import ClientCreate, ClientResponse, ClientUpdate
from app.db import get_db
from app.users.models import User

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post(
    "/",
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_client(
    client_data: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ClientResponse:
    """
    Create a new client.

    Args:
        client_data: Client creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created client information

    Raises:
        HTTPException: If client with same email already exists
    """
    repository = ClientRepository(db)

    # Check if client with same email already exists
    existing_client = repository.get_by_email(client_data.email)
    if existing_client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client with this email already exists",
        )

    client = repository.create(client_data)
    return ClientResponse.model_validate(client)


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


