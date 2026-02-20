"""Pydantic schemas for attendance validation and serialization."""

import enum
import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.attendances.models import AttendanceStatus
from app.clients.models import ClientStatus, InterestType, PropertyType


class ClientStatusUpdate(BaseModel):
    """Schema for updating client status from attendance."""

    current_status: ClientStatus | None = Field(None, description="Novo estágio do cliente no funil")
    current_interest_type: InterestType | None = Field(None, description="Tipo de interesse (BUY, RENT, etc.)")
    current_property_type: PropertyType | None = Field(None, description="Tipo de imóvel de interesse")


class AttendanceBase(BaseModel):
    """Base schema for attendance data."""

    client_id: uuid.UUID = Field(..., description="Client ID (required)")
    agent_id: uuid.UUID = Field(..., description="Agent ID (required, must be corretor)")
    property_id: uuid.UUID | None = Field(None, description="Property ID (nullable)")
    objective: str | None = Field(
        None,
        description="Clear objective of this interaction cycle (e.g., 'Purchase residential property in City X'). Can be auto-detected from content if not provided.",
    )
    raw_content: str = Field(
        ...,
        min_length=1,
        max_length=100000,  # 100k chars limit to avoid performance issues
        description="Raw content of conversations (can accumulate over time within the same cycle). Maximum 100,000 characters.",
    )
    ai_summary: str | None = Field(None, description="AI-generated summary")
    ai_next_steps: str | None = Field(None, description="AI-generated next steps")
    status: AttendanceStatus = Field(
        AttendanceStatus.ACTIVE,
        description="Attendance status (defaults to ACTIVE)",
    )
    updated_client_status: ClientStatusUpdate | None = Field(
        None,
        description="Client status updates (current_status, current_interest_type, current_property_type)",
    )
    scheduled_visit_at: datetime | None = Field(
        None,
        description="Scheduled visit date/time (will create a visit if provided)",
    )



class AttendanceCreate(AttendanceBase):
    """
    Schema for creating a new attendance.

    **Cycle Logic:**
    - Client has only one active attendance at a time.
    - If the client has an active attendance, new content is accumulated into it.
    - A new cycle is created only when no active attendance exists (previous closed).
    - If no objective is provided, it will be auto-detected from the raw_content.

    **Required fields:** client_id, agent_id, raw_content.
    
    **Automatic behaviors:**
    - AI summary is generated automatically.
    - Objective is auto-detected if not provided.
    """

    pass


class AttendanceUpdate(BaseModel):
    """
    Schema for updating attendance information.

    All fields are optional (partial update). Status → COMPLETED pode regenerar resumo IA.
    """

    client_id: uuid.UUID | None = Field(None, description="ID do cliente")
    agent_id: uuid.UUID | None = Field(None, description="ID do agente (deve ser corretor)")
    property_id: uuid.UUID | None = Field(None, description="ID do imóvel")
    objective: str | None = Field(None, description="Objetivo do ciclo (alterar não recria ciclo automaticamente)")
    raw_content: str | None = Field(
        None,
        min_length=1,
        max_length=100000,
        description="Conteúdo bruto da conversa (máx. 100.000 caracteres); atualizar pode disparar detecção visita/perda/venda",
    )
    ai_summary: str | None = Field(None, description="Resumo gerado pela IA")
    ai_next_steps: str | None = Field(None, description="Próximos passos sugeridos pela IA")
    status: AttendanceStatus | None = Field(None, description="ACTIVE, COMPLETED, LOST ou ABANDONED")
    updated_client_status: ClientStatusUpdate | None = Field(None, description="Atualizações de status/interesse do cliente")
    scheduled_visit_at: datetime | None = Field(None, description="Data/hora da visita agendada (pode criar visita)")



class CycleAction(str, enum.Enum):
    """Ação de ciclo ao criar/atualizar atendimento (retornada no POST)."""

    NEW_CYCLE_CREATED = "NEW_CYCLE_CREATED"
    CYCLE_UPDATED = "CYCLE_UPDATED"
    PREVIOUS_CYCLE_CLOSED = "PREVIOUS_CYCLE_CLOSED"


class DetectedVisitInfo(BaseModel):
    """Sugestão de visita detectada pela IA (não cria visita automaticamente)."""

    detected: bool = Field(..., description="Se foi detectada intenção de agendar visita")
    scheduled_at: str | None = Field(None, description="Data/hora sugerida (ISO)")
    date: str | None = Field(None, description="Data legível (DD/MM/YYYY)")
    time: str | None = Field(None, description="Hora legível (HH:MM)")
    confidence: float | None = Field(None, description="Confiança 0–1")
    extracted_text: str | None = Field(None, description="Trecho da conversa extraído")
    property_id: str | None = Field(None, description="ID do imóvel se mencionado")
    notes: str | None = Field(None, description="Observações da detecção")


class DetectedLossInfo(BaseModel):
    """Sugestão de perda detectada pela IA (atendimento permanece ACTIVE até confirmação)."""

    detected: bool = Field(..., description="Se foi detectada intenção de perda")
    loss_reason: str | None = Field(None, description="Motivo sugerido (valor do enum LossReason)")
    loss_stage: str | None = Field(None, description="Estágio sugerido (valor do enum LossStage)")
    confidence: float | None = Field(None, description="Confiança 0–1")
    extracted_text: str | None = Field(None, description="Trecho que indicou perda")
    detailed_reason: str | None = Field(None, description="Explicação detalhada extraída")
    client_feedback: str | None = Field(None, description="Feedback do cliente extraído")


class DetectedSaleInfo(BaseModel):
    """Sugestão de venda/aluguel detectada pela IA (atendimento permanece ACTIVE até confirmação)."""

    detected: bool = Field(..., description="Se foi detectada intenção de venda/aluguel")
    sale_type: str | None = Field(None, description="Tipo sugerido (SALE ou RENT)")
    sale_value: float | None = Field(None, description="Valor sugerido extraído do conteúdo")
    property_id: uuid.UUID | None = Field(None, description="ID do imóvel do atendimento ou visita vinculada")
    confidence: float | None = Field(None, description="Confiança 0–1")
    extracted_text: str | None = Field(None, description="Trecho que indicou venda")
    payment_method: str | None = Field(None, description="Forma de pagamento mencionada (CASH, FINANCING, etc.)")
    notes: str | None = Field(None, description="Informações adicionais extraídas")


class AttendanceResponse(BaseModel):
    """
    Resposta de atendimento: campos base, id, timestamps e (quando aplicável) ciclo e sugestões IA.
    """

    id: uuid.UUID = Field(..., description="UUID do atendimento")
    client_id: uuid.UUID = Field(..., description="ID do cliente")
    agent_id: uuid.UUID = Field(..., description="ID do agente (corretor)")
    property_id: uuid.UUID | None = Field(None, description="ID do imóvel (opcional)")
    objective: str | None = Field(None, description="Objetivo do ciclo de interação")
    raw_content: str = Field(..., min_length=1, description="Conteúdo bruto das conversas")
    ai_summary: str | None = Field(None, description="Resumo gerado pela IA")
    ai_next_steps: str | None = Field(None, description="Próximos passos sugeridos pela IA")
    status: AttendanceStatus = Field(
        AttendanceStatus.ACTIVE,
        description="ACTIVE, COMPLETED, LOST ou ABANDONED",
    )
    updated_client_status: ClientStatusUpdate | None = Field(
        None,
        description="Atualizações de status/interesse do cliente (JSON)",
    )
    scheduled_visit_at: datetime | None = Field(None, description="Data/hora da visita agendada")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: datetime = Field(..., description="Data da última atualização")
    cycle_action: CycleAction | None = Field(
        None,
        description="Ação no ciclo (NEW_CYCLE_CREATED, CYCLE_UPDATED, PREVIOUS_CYCLE_CLOSED); presente no POST.",
    )
    previous_cycle_id: uuid.UUID | None = Field(
        None,
        description="ID do ciclo anterior fechado (quando NEW_CYCLE_CREATED)",
    )
    detected_visit: DetectedVisitInfo | None = Field(
        None,
        description="Sugestão de visita detectada pela IA (confirmação pelo usuário)",
    )
    detected_loss: DetectedLossInfo | None = Field(
        None,
        description="Sugestão de perda detectada pela IA (confirmação pelo usuário)",
    )
    detected_sale: DetectedSaleInfo | None = Field(
        None,
        description="Sugestão de venda detectada pela IA (confirmação pelo usuário)",
    )

    @model_validator(mode="before")
    @classmethod
    def parse_updated_client_status(cls, data: Any) -> Any:
        """Parse updated_client_status from JSON string if needed."""
        # Handle SQLAlchemy model instance
        if hasattr(data, "__dict__"):
            if hasattr(data, "updated_client_status"):
                updated_status = data.updated_client_status
                if isinstance(updated_status, str) and updated_status.strip():
                    try:
                        parsed = json.loads(updated_status)
                        data.updated_client_status = ClientStatusUpdate(**parsed) if parsed else None
                    except (json.JSONDecodeError, TypeError, ValueError):
                        data.updated_client_status = None
                elif updated_status is None or updated_status == "":
                    data.updated_client_status = None
        # Handle dict
        elif isinstance(data, dict) and "updated_client_status" in data:
            updated_status = data["updated_client_status"]
            if isinstance(updated_status, str) and updated_status.strip():
                try:
                    parsed = json.loads(updated_status)
                    data["updated_client_status"] = ClientStatusUpdate(**parsed) if parsed else None
                except (json.JSONDecodeError, TypeError, ValueError):
                    data["updated_client_status"] = None
            elif updated_status is None or updated_status == "":
                data["updated_client_status"] = None
        return data

    class Config:
        """Pydantic config."""

        from_attributes = True

