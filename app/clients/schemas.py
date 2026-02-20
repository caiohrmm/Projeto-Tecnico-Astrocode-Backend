"""Pydantic schemas for client validation and serialization."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, field_validator

from app.clients.models import (
    ClientStatus,
    InterestType,
    LeadSource,
    PropertyType,
    UrgencyLevel,
)


class ClientBase(BaseModel):
    """Base schema with common client fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Nome do cliente")
    phone: str = Field(..., min_length=1, max_length=20, description="Telefone")
    email: str | None = Field(None, max_length=255, description="E-mail (único no sistema)")
    lead_source: LeadSource = Field(..., description="Origem do lead (ex.: WHATSAPP, WEBSITE)")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        """Validate email format if provided, allow None."""
        if v is None or v == "":
            return None
        # Basic email format validation
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v


class ClientCreate(ClientBase):
    """
    Schema for creating a new client.

    Only required fields: name, phone, email, lead_source.
    All other fields are optional and can be set later.
    """

    # Initial message for AI classification
    initial_message: str | None = Field(
        None,
        description="First message from the client (used for AI classification)",
    )
    
    # Flag to enable/disable AI classification
    use_ai_classification: bool = Field(
        True,
        description="Whether to use AI for initial lead classification",
    )

    # Funnel Status & Scoring (optional)
    current_status: ClientStatus | None = Field(
        None,
        description="Current stage in sales funnel (defaults to NEW_LEAD)",
    )
    current_lead_score: int | None = Field(
        None,
        ge=0,
        le=100,
        description="Lead score from 0 to 100 (controlled exclusively by AI)",
    )
    current_urgency_level: UrgencyLevel | None = Field(
        None,
        description="Urgency level (LOW, MEDIUM, HIGH, IMMEDIATE)",
    )

    # Client Interest (optional)
    current_interest_type: InterestType | None = Field(
        None,
        description="Type of interest (BUY, RENT, SELL, INVEST)",
    )
    current_property_type: PropertyType | None = Field(
        None,
        description="Property type of interest",
    )
    current_budget_min: Decimal | None = Field(
        None,
        ge=0,
        description="Minimum budget",
    )
    current_budget_max: Decimal | None = Field(
        None,
        ge=0,
        description="Maximum budget",
    )
    current_city_interest: str | None = Field(
        None,
        max_length=255,
        description="City where client wants property",
    )

    # Relationship Management (optional)
    first_contact_at: datetime | None = Field(
        None,
        description="Date of first contact",
    )
    last_contact_at: datetime | None = Field(
        None,
        description="Date of last contact",
    )
    summary_notes: str | None = Field(
        None,
        description="Summary notes about the client",
    )

    @field_validator("current_budget_max")
    @classmethod
    def validate_budget_range(cls, v: Decimal | None, info) -> Decimal | None:
        """Validate that max budget is greater than or equal to min budget."""
        if v is not None and "current_budget_min" in info.data:
            min_budget = info.data.get("current_budget_min")
            if min_budget is not None and v < min_budget:
                raise ValueError("current_budget_max must be >= current_budget_min")
        return v


class ClientUpdate(BaseModel):
    """
    Schema for updating client information.

    All fields are optional to allow partial updates.
    """

    name: str | None = Field(None, min_length=1, max_length=255, description="Nome do cliente")
    phone: str | None = Field(None, min_length=1, max_length=20, description="Telefone")
    email: EmailStr | None = Field(None, description="E-mail (deve ser único)")
    lead_source: LeadSource | None = Field(None, description="Origem do lead")

    # Funnel Status & Scoring
    current_status: ClientStatus | None = Field(None, description="Estágio no funil de vendas")
    current_lead_score: int | None = Field(
        None,
        ge=0,
        le=100,
        description="Lead score 0–100 (controlado pela IA; atualizações manuais podem ser ignoradas)",
    )
    current_urgency_level: UrgencyLevel | None = Field(None, description="Nível de urgência (LOW, MEDIUM, HIGH, IMMEDIATE)")

    # Client Interest
    current_interest_type: InterestType | None = Field(None, description="Tipo de interesse (BUY, RENT, SELL, INVEST)")
    current_property_type: PropertyType | None = Field(None, description="Tipo de imóvel de interesse")
    current_budget_min: Decimal | None = Field(None, ge=0, description="Orçamento mínimo")
    current_budget_max: Decimal | None = Field(None, ge=0, description="Orçamento máximo (deve ser ≥ mínimo)")
    current_city_interest: str | None = Field(None, max_length=255, description="Cidade de interesse")

    # Relationship Management
    first_contact_at: datetime | None = Field(None, description="Data do primeiro contato")
    last_contact_at: datetime | None = Field(None, description="Data do último contato")
    summary_notes: str | None = Field(None, description="Resumo/notas sobre o cliente")

    # State Derivation Tracking (set automatically by system)
    last_state_derivation_at: datetime | None = Field(None, description="Última derivação de estado pela IA")
    state_derivation_count: int | None = Field(None, ge=0, description="Quantidade de derivações realizadas")
    state_derived_from_attendances_count: int | None = Field(None, ge=0, description="Atendimentos usados na última derivação")

    @field_validator("current_budget_max")
    @classmethod
    def validate_budget_range(cls, v: Decimal | None, info) -> Decimal | None:
        """Validate that max budget is greater than or equal to min budget."""
        if v is not None and "current_budget_min" in info.data:
            min_budget = info.data.get("current_budget_min")
            if min_budget is not None and v < min_budget:
                raise ValueError("current_budget_max must be >= current_budget_min")
        return v


class ClientResponse(ClientBase):
    """
    Schema for client response (serialization).

    Includes all client information with timestamps and optional fields.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID do cliente")

    # Funnel Status & Scoring
    current_status: ClientStatus | None = Field(None, description="Estágio atual no funil")
    current_lead_score: int | None = Field(None, description="Score do lead 0–100 (derivado pela IA)")
    current_urgency_level: UrgencyLevel | None = Field(None, description="Nível de urgência")

    # Commercial Assignment
    assigned_agent_id: uuid.UUID | None = Field(None, description="ID do agente atribuído")

    # Client Interest
    current_interest_type: InterestType | None = Field(None, description="Tipo de interesse (compra/aluguel/etc.)")
    current_property_type: PropertyType | None = Field(None, description="Tipo de imóvel preferido")
    current_budget_min: Decimal | None = Field(None, description="Orçamento mínimo")
    current_budget_max: Decimal | None = Field(None, description="Orçamento máximo")
    current_city_interest: str | None = Field(None, description="Cidade de interesse")

    # Relationship Management
    first_contact_at: datetime | None = Field(None, description="Primeiro contato")
    last_contact_at: datetime | None = Field(None, description="Último contato")
    summary_notes: str | None = Field(None, description="Notas resumidas")
    initial_message: str | None = Field(None, description="Primeira mensagem do cliente")

    # State Derivation Tracking (for visibility/transparency)
    last_state_derivation_at: datetime | None = Field(
        None,
        description="Data/hora da última derivação de estado pela IA",
    )
    state_derivation_count: int = Field(
        0,
        ge=0,
        description="Quantidade de vezes que o estado foi derivado pela IA",
    )
    state_derived_from_attendances_count: int | None = Field(
        None,
        ge=0,
        description="Quantidade de atendimentos usados na última derivação",
    )

    # Timestamps
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: datetime = Field(..., description="Data da última atualização")


class ClientInDB(ClientResponse):
    """
    Schema for client stored in database.

    Same as ClientResponse, kept for consistency with other domains.
    """

    pass


class LeadClassificationResult(BaseModel):
    """Schema for AI lead classification result."""

    lead_score: int = Field(..., ge=0, le=100, description="Score do lead 0–100")
    urgency_level: UrgencyLevel = Field(..., description="Nível de urgência (LOW, MEDIUM, HIGH, IMMEDIATE)")
    interest_type: InterestType | None = Field(None, description="Tipo de interesse (BUY, RENT, etc.)")
    property_type: PropertyType | None = Field(None, description="Tipo de imóvel preferido")
    suggested_status: ClientStatus = Field(ClientStatus.NEW_LEAD, description="Status sugerido no funil")

    classification_reason: str = Field(..., description="Motivo/explicação da classificação pela IA")
    key_indicators: list[str] = Field(default_factory=list, description="Indicadores-chave detectados")
    recommended_actions: list[str] = Field(default_factory=list, description="Ações recomendadas")
    confidence: float = Field(..., ge=0, le=1, description="Confiança da classificação 0–1")


class ClientWithClassification(ClientResponse):
    """Schema for client response with AI classification details."""

    ai_classification: LeadClassificationResult | None = Field(
        None,
        description="Classificação da IA (na criação retorna null; perfil é atualizado pelos atendimentos)",
    )


class ClassifyLeadRequest(BaseModel):
    """Schema for lead classification request (opcional; mantido por compatibilidade)."""

    initial_message: str | None = Field(None, description="Mensagem para análise (não usado na derivação atual)")
    notes: str | None = Field(None, description="Notas adicionais")


