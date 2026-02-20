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
    """Schema for updating a sale. All fields optional; status transitions trigger side effects (SIGNED/COMPLETED/CANCELLED)."""

    property_id: uuid.UUID | None = Field(None, description="ID do imóvel")
    broker_id: uuid.UUID | None = Field(None, description="ID do corretor")

    status: SaleStatus | None = Field(None, description="PENDING, SIGNED, COMPLETED ou CANCELLED (efeitos automáticos)")
    sale_value: Decimal | None = Field(None, gt=0, description="Valor total da venda/aluguel")

    commission_percentage: Decimal | None = Field(None, ge=0, le=100, description="Percentual de comissão")
    commission_value: Decimal | None = Field(None, description="Valor da comissão")
    down_payment: Decimal | None = Field(None, description="Entrada (legado)")
    payment_method: PaymentMethod | None = Field(None, description="Forma de pagamento única (legado)")
    payment_methods: list[PaymentMethodItem] | None = Field(None, description="Lista de formas de pagamento")

    rent_duration_months: int | None = Field(None, description="Duração do aluguel em meses")
    rent_start_date: datetime | None = Field(None, description="Data de início do aluguel")

    proposal_date: datetime | None = Field(None, description="Data da proposta")
    contract_date: datetime | None = Field(None, description="Data do contrato (definida ao marcar SIGNED)")
    completion_date: datetime | None = Field(None, description="Data de conclusão (definida ao marcar COMPLETED)")
    notes: str | None = Field(None, description="Observações")
    ai_analysis: str | None = Field(None, description="Análise de sucesso pela IA (preenchida ao concluir)")
    ai_success_factors: str | None = Field(None, description="Fatores de sucesso pela IA (preenchidos ao concluir)")


class SaleResponse(SaleBase):
    """Schema for sale response (inclui nomes de cliente, imóvel e corretor)."""

    id: uuid.UUID = Field(..., description="UUID da venda")
    status: SaleStatus = Field(..., description="PENDING, SIGNED, COMPLETED ou CANCELLED")
    commission_value: Decimal | None = Field(None, description="Valor da comissão calculado")
    contract_date: datetime | None = Field(None, description="Data do contrato")
    completion_date: datetime | None = Field(None, description="Data de conclusão")
    ai_analysis: str | None = Field(None, description="Análise de sucesso pela IA")
    ai_success_factors: str | None = Field(None, description="Fatores de sucesso pela IA")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: datetime = Field(..., description="Data da última atualização")

    # Related entities names for display
    client_name: str | None = Field(None, description="Nome do cliente")
    property_title: str | None = Field(None, description="Título do imóvel")
    broker_name: str | None = Field(None, description="Nome do corretor")

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
    """Schema for sale with full details (telefone/e-mail do cliente, endereço/cidade do imóvel)."""

    client_phone: str | None = Field(None, description="Telefone do cliente")
    client_email: str | None = Field(None, description="E-mail do cliente")
    property_address: str | None = Field(None, description="Endereço do imóvel")
    property_city: str | None = Field(None, description="Cidade do imóvel")

    class Config:
        from_attributes = True


class SaleStats(BaseModel):
    """Estatísticas agregadas de vendas e aluguéis."""

    total_sales: int = Field(0, description="Quantidade total de registros")
    total_value: Decimal = Field(Decimal("0.00"), description="Valor total (vendas + aluguéis)")
    total_commission: Decimal = Field(Decimal("0.00"), description="Comissão total")

    sales_count: int = Field(0, description="Quantidade de vendas (SALE)")
    rent_count: int = Field(0, description="Quantidade de aluguéis (RENT)")

    pending_count: int = Field(0, description="Vendas pendentes (PENDING/SIGNED)")
    completed_count: int = Field(0, description="Vendas concluídas (COMPLETED)")

    avg_sale_value: Decimal = Field(Decimal("0.00"), description="Valor médio por venda/aluguel")
    avg_commission: Decimal = Field(Decimal("0.00"), description="Comissão média")

