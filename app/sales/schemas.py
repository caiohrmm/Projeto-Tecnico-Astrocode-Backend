"""Pydantic schemas for Sales."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.sales.models import PaymentMethod, SaleStatus, SaleType


class PaymentMethodItem(BaseModel):
    """Schema for a single payment method item."""
    
    method: PaymentMethod = Field(..., description="Payment method type")
    value: Decimal = Field(..., gt=0, description="Payment value for this method")
    description: str | None = Field(None, description="Optional description for this payment method")


class SaleBase(BaseModel):
    """Base schema for Sale."""

    client_id: uuid.UUID = Field(..., description="Client ID (required)")
    property_id: uuid.UUID | None = Field(None, description="Property ID")
    broker_id: uuid.UUID | None = Field(None, description="Broker ID")
    
    sale_type: SaleType = Field(..., description="Type of sale (SALE or RENT)")
    sale_value: Decimal = Field(..., gt=0, description="Total sale/rent value")
    
    commission_percentage: Decimal | None = Field(
        Decimal("5.00"),
        ge=0,
        le=100,
        description="Commission percentage (0-100)",
    )
    down_payment: Decimal | None = Field(None, ge=0, description="Down payment amount (legacy, use payment_methods)")
    payment_method: PaymentMethod | None = Field(None, description="Legacy single payment method (deprecated, use payment_methods)")
    payment_methods: list[PaymentMethodItem] | None = Field(
        None,
        description="List of payment methods. Each item has method, value, and optional description. Example: [{'method': 'CASH', 'value': 100000.00, 'description': 'Entrada'}, {'method': 'FINANCING', 'value': 400000.00}]",
    )
    
    rent_duration_months: int | None = Field(None, ge=1, description="Rent duration in months")
    rent_start_date: datetime | None = Field(None, description="Rent start date")
    
    proposal_date: datetime | None = Field(None, description="Proposal acceptance date")
    notes: str | None = Field(None, description="Additional notes")


class SaleCreate(SaleBase):
    """Schema for creating a sale."""

    @field_validator("commission_percentage", mode="before")
    @classmethod
    def set_default_commission(cls, v):
        if v is None:
            return Decimal("5.00")
        return v


class SaleUpdate(BaseModel):
    """Schema for updating a sale."""

    property_id: uuid.UUID | None = None
    broker_id: uuid.UUID | None = None
    
    status: SaleStatus | None = None
    sale_value: Decimal | None = Field(None, gt=0)
    
    commission_percentage: Decimal | None = Field(None, ge=0, le=100)
    commission_value: Decimal | None = None
    down_payment: Decimal | None = None
    payment_method: PaymentMethod | None = None
    payment_methods: list[PaymentMethodItem] | None = None
    
    rent_duration_months: int | None = None
    rent_start_date: datetime | None = None
    
    proposal_date: datetime | None = None
    contract_date: datetime | None = None
    completion_date: datetime | None = None
    
    notes: str | None = None
    ai_analysis: str | None = None
    ai_success_factors: str | None = None


class SaleResponse(SaleBase):
    """Schema for sale response."""

    id: uuid.UUID
    status: SaleStatus
    commission_value: Decimal | None = None
    contract_date: datetime | None = None
    completion_date: datetime | None = None
    ai_analysis: str | None = None
    ai_success_factors: str | None = None
    created_at: datetime
    updated_at: datetime

    # Related entities names for display
    client_name: str | None = None
    property_title: str | None = None
    broker_name: str | None = None

    @field_validator("payment_methods", mode="before")
    @classmethod
    def convert_payment_methods_from_dict(cls, v):
        """Convert payment_methods from dict format (from DB) to PaymentMethodItem list."""
        if v is None:
            return None
        if isinstance(v, list):
            # Already a list, check if it's dicts or PaymentMethodItem
            if v and isinstance(v[0], dict):
                # Convert dicts to PaymentMethodItem
                from app.sales.models import PaymentMethod
                return [
                    PaymentMethodItem(
                        method=PaymentMethod(item["method"]),
                        value=Decimal(str(item["value"])),
                        description=item.get("description"),
                    )
                    for item in v
                ]
        return v

    class Config:
        from_attributes = True


class SaleWithDetails(SaleResponse):
    """Schema for sale with full details."""

    # Client details
    client_phone: str | None = None
    client_email: str | None = None
    
    # Property details
    property_address: str | None = None
    property_city: str | None = None
    
    class Config:
        from_attributes = True


class SaleStats(BaseModel):
    """Schema for sales statistics."""

    total_sales: int = 0
    total_value: Decimal = Decimal("0.00")
    total_commission: Decimal = Decimal("0.00")
    
    sales_count: int = 0
    rent_count: int = 0
    
    pending_count: int = 0
    completed_count: int = 0
    
    avg_sale_value: Decimal = Decimal("0.00")
    avg_commission: Decimal = Decimal("0.00")

