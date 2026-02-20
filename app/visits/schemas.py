"""Pydantic schemas for visit validation and serialization."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.visits.models import VisitStatus


class VisitBase(BaseModel):
    """Base schema for visit data."""

    attendance_id: uuid.UUID | None = Field(
        None,
        description="ID do atendimento (opcional; se informado, atendimento deve estar ACTIVE e sem visita pendente)",
    )
    property_id: uuid.UUID | None = Field(
        None,
        description="ID do imóvel (opcional)",
    )
    client_id: uuid.UUID = Field(
        ...,
        description="ID do cliente",
    )
    broker_id: uuid.UUID = Field(
        ...,
        description="ID do corretor (usuário com role corretor)",
    )
    scheduled_at: datetime = Field(
        ...,
        description="Data e hora agendadas da visita",
    )
    status: VisitStatus = Field(
        VisitStatus.SCHEDULED,
        description="Status da visita (SCHEDULED, CONFIRMED, IN_PROGRESS, COMPLETED, CANCELLED, NO_SHOW)",
    )
    notes: str | None = Field(
        None,
        description="Observações sobre a visita",
    )


class VisitCreate(VisitBase):
    """
    Schema for creating a new visit.

    Required fields: client_id, broker_id, scheduled_at.
    All other fields are optional.
    """

    pass


class VisitUpdate(BaseModel):
    """
    Schema for updating visit information.

    All fields are optional. Se a visita estiver vinculada a um atendimento, apenas scheduled_at e status são aplicados.
    """

    attendance_id: uuid.UUID | None = Field(None, description="ID do atendimento (só aplicado se visita não vinculada)")
    property_id: uuid.UUID | None = Field(None, description="ID do imóvel")
    client_id: uuid.UUID | None = Field(None, description="ID do cliente")
    broker_id: uuid.UUID | None = Field(None, description="ID do corretor (deve ser corretor)")
    scheduled_at: datetime | None = Field(None, description="Nova data/hora agendada (reagendamento)")
    status: VisitStatus | None = Field(None, description="Novo status")
    notes: str | None = Field(None, description="Observações")


class VisitResponse(VisitBase):
    """
    Schema for visit response.

    Includes all base fields plus id and timestamps.
    """

    id: uuid.UUID = Field(..., description="UUID da visita")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: datetime = Field(..., description="Data da última atualização")

    class Config:
        """Pydantic config."""

        from_attributes = True

