"""Sales routes for CRUD operations."""

import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db import get_db
from app.sales.models import Sale, SaleStatus, SaleType
from app.sales.repository import SaleRepository
from app.sales.schemas import SaleCreate, SaleResponse, SaleStats, SaleUpdate, SaleWithDetails
from app.users.models import User

router = APIRouter(prefix="/sales", tags=["sales"])


def _enrich_sale_response(sale: Sale) -> dict:
    """Enrich sale with related entity names."""
    data = {
        "id": sale.id,
        "client_id": sale.client_id,
        "property_id": sale.property_id,
        "broker_id": sale.broker_id,
        "sale_type": sale.sale_type,
        "status": sale.status,
        "sale_value": sale.sale_value,
        "commission_percentage": sale.commission_percentage,
        "commission_value": sale.commission_value,
        "down_payment": sale.down_payment,
        "payment_method": sale.payment_method,
        "payment_methods": sale.payment_methods,
        "rent_duration_months": sale.rent_duration_months,
        "rent_start_date": sale.rent_start_date,
        "proposal_date": sale.proposal_date,
        "contract_date": sale.contract_date,
        "completion_date": sale.completion_date,
        "notes": sale.notes,
        "ai_analysis": sale.ai_analysis,
        "ai_success_factors": sale.ai_success_factors,
        "created_at": sale.created_at,
        "updated_at": sale.updated_at,
        # Enriched fields
        "client_name": sale.client.name if sale.client else None,
        "property_title": sale.property.title if sale.property else None,
        "broker_name": sale.broker.full_name if sale.broker else None,
    }
    return data


@router.post("/", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def create_sale(
    sale_data: SaleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SaleResponse:
    """
    Create a new sale record.

    This endpoint:
    - Creates the sale record
    - Updates client status to WON
    - Updates property status to SOLD/RENTED
    - Calculates commission value
    - Adds timeline event
    """
    sale_repo = SaleRepository(db)
    sale = sale_repo.create(sale_data)
    return SaleResponse(**_enrich_sale_response(sale))


@router.get("/", response_model=List[SaleResponse])
def list_sales(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    client_id: uuid.UUID | None = Query(None, description="Filter by client ID"),
    property_id: uuid.UUID | None = Query(None, description="Filter by property ID"),
    broker_id: uuid.UUID | None = Query(None, description="Filter by broker ID"),
    sale_type: SaleType | None = Query(None, description="Filter by sale type"),
    sale_status: SaleStatus | None = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[SaleResponse]:
    """List all sales with optional filters."""
    sale_repo = SaleRepository(db)
    sales = sale_repo.get_all(
        skip=skip,
        limit=limit,
        client_id=client_id,
        property_id=property_id,
        broker_id=broker_id,
        sale_type=sale_type,
        status=sale_status,
    )
    return [SaleResponse(**_enrich_sale_response(sale)) for sale in sales]


@router.get("/stats", response_model=SaleStats)
def get_sales_stats(
    broker_id: uuid.UUID | None = Query(None, description="Filter by broker ID"),
    start_date: datetime | None = Query(None, description="Start date filter"),
    end_date: datetime | None = Query(None, description="End date filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SaleStats:
    """Get sales statistics."""
    sale_repo = SaleRepository(db)
    return sale_repo.get_stats(
        broker_id=broker_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/{sale_id}", response_model=SaleWithDetails)
def get_sale(
    sale_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SaleWithDetails:
    """Get a sale by ID with full details."""
    sale_repo = SaleRepository(db)
    sale = sale_repo.get_by_id(sale_id)
    
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found",
        )
    
    data = _enrich_sale_response(sale)
    
    # Add extra details
    if sale.client:
        data["client_phone"] = sale.client.phone
        data["client_email"] = sale.client.email
    
    if sale.property:
        data["property_address"] = f"{sale.property.street}, {sale.property.number}" if sale.property.street else None
        data["property_city"] = sale.property.city
    
    return SaleWithDetails(**data)


@router.put("/{sale_id}", response_model=SaleResponse)
def update_sale(
    sale_id: uuid.UUID,
    sale_data: SaleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SaleResponse:
    """
    Update a sale.

    Handles status transitions:
    - SIGNED: Sets contract_date, adds timeline event
    - COMPLETED: Sets completion_date, triggers AI analysis
    - CANCELLED: Reverts client/property status
    """
    sale_repo = SaleRepository(db)
    sale = sale_repo.get_by_id(sale_id)
    
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found",
        )
    
    updated_sale = sale_repo.update(sale, sale_data)
    return SaleResponse(**_enrich_sale_response(updated_sale))


@router.delete("/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sale(
    sale_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """
    Delete a sale.

    This will:
    - Revert client status if sale was not cancelled
    - Revert property status if sale was not cancelled
    """
    sale_repo = SaleRepository(db)
    sale = sale_repo.get_by_id(sale_id)
    
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found",
        )
    
    sale_repo.delete(sale)


@router.post("/{sale_id}/complete", response_model=SaleResponse)
def complete_sale(
    sale_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SaleResponse:
    """
    Mark a sale as completed.

    This is a convenience endpoint that:
    - Sets status to COMPLETED
    - Sets completion_date
    - Triggers AI analysis
    """
    sale_repo = SaleRepository(db)
    sale = sale_repo.get_by_id(sale_id)
    
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found",
        )
    
    if sale.status == SaleStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot complete a cancelled sale",
        )
    
    updated_sale = sale_repo.update(sale, SaleUpdate(status=SaleStatus.COMPLETED))
    return SaleResponse(**_enrich_sale_response(updated_sale))


@router.post("/{sale_id}/cancel", response_model=SaleResponse)
def cancel_sale(
    sale_id: uuid.UUID,
    reason: str | None = Query(None, description="Cancellation reason"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SaleResponse:
    """
    Cancel a sale.

    This will:
    - Set status to CANCELLED
    - Revert client status to LOST
    - Revert property status to PUBLISHED
    """
    sale_repo = SaleRepository(db)
    sale = sale_repo.get_by_id(sale_id)
    
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found",
        )
    
    if sale.status == SaleStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a completed sale",
        )
    
    update_data = SaleUpdate(status=SaleStatus.CANCELLED)
    if reason:
        update_data.notes = f"Cancelado: {reason}"
    
    updated_sale = sale_repo.update(sale, update_data)
    return SaleResponse(**_enrich_sale_response(updated_sale))

