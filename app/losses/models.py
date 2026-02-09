"""Loss model for tracking lost deals and reasons."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.clients.models import Client
    from app.properties.models import Property
    from app.users.models import User


class LossReason(str, enum.Enum):
    """Enum for loss reasons."""

    # Price related
    PRICE_TOO_HIGH = "PRICE_TOO_HIGH"  # Preço muito alto
    BUDGET_INSUFFICIENT = "BUDGET_INSUFFICIENT"  # Orçamento insuficiente
    BETTER_OFFER_COMPETITOR = "BETTER_OFFER_COMPETITOR"  # Melhor oferta da concorrência

    # Property related
    PROPERTY_NOT_SUITABLE = "PROPERTY_NOT_SUITABLE"  # Imóvel não adequado
    LOCATION_NOT_IDEAL = "LOCATION_NOT_IDEAL"  # Localização não ideal
    NO_MATCHING_PROPERTY = "NO_MATCHING_PROPERTY"  # Nenhum imóvel compatível

    # Client related
    CLIENT_CHANGED_MIND = "CLIENT_CHANGED_MIND"  # Cliente mudou de ideia
    CLIENT_NOT_READY = "CLIENT_NOT_READY"  # Cliente não está pronto
    CLIENT_UNRESPONSIVE = "CLIENT_UNRESPONSIVE"  # Cliente não responde
    CLIENT_FINANCING_DENIED = "CLIENT_FINANCING_DENIED"  # Financiamento negado

    # Service related
    SLOW_RESPONSE = "SLOW_RESPONSE"  # Resposta lenta
    POOR_SERVICE = "POOR_SERVICE"  # Atendimento ruim

    # External
    ECONOMIC_FACTORS = "ECONOMIC_FACTORS"  # Fatores econômicos
    PERSONAL_REASONS = "PERSONAL_REASONS"  # Motivos pessoais

    # Other
    OTHER = "OTHER"  # Outro motivo


class LossStage(str, enum.Enum):
    """Enum for the stage at which the client was lost."""

    INITIAL_CONTACT = "INITIAL_CONTACT"  # Contato inicial
    QUALIFICATION = "QUALIFICATION"  # Qualificação
    VISIT_SCHEDULED = "VISIT_SCHEDULED"  # Visita agendada
    VISIT_COMPLETED = "VISIT_COMPLETED"  # Visita realizada
    PROPOSAL = "PROPOSAL"  # Proposta
    NEGOTIATION = "NEGOTIATION"  # Negociação
    CONTRACT = "CONTRACT"  # Contrato


class ClientLoss(Base):
    """
    ClientLoss model for tracking lost deals.

    This model helps understand why deals are lost and enables
    AI analysis of loss patterns to improve conversion.

    Attributes:
        id: Unique identifier (UUID)
        client_id: Foreign key to Client
        property_id: Property that was being negotiated (optional)
        broker_id: Broker who was handling the deal
        
        loss_reason: Primary reason for loss
        loss_stage: Stage at which the client was lost
        
        detailed_reason: Detailed explanation of the loss
        client_feedback: Direct feedback from the client
        competitor_info: Info about competitor if applicable
        
        could_have_been_prevented: Whether the loss could have been prevented
        lessons_learned: Lessons learned from this loss
        
        ai_analysis: AI-generated analysis of the loss
        ai_recommendations: AI recommendations to prevent similar losses
        
        lost_at: When the client was lost
        created_at: When the record was created
    """

    __tablename__ = "client_losses"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Relationships
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    property_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    broker_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Loss details
    loss_reason: Mapped[LossReason] = mapped_column(
        Enum(LossReason, native_enum=False, length=50),
        nullable=False,
        index=True,
    )
    loss_stage: Mapped[LossStage] = mapped_column(
        Enum(LossStage, native_enum=False, length=30),
        nullable=False,
        index=True,
    )

    # Detailed information
    detailed_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed explanation of why the deal was lost",
    )
    client_feedback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Direct feedback from the client",
    )
    competitor_info: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Information about competitor if applicable",
    )

    # Analysis fields
    could_have_been_prevented: Mapped[bool | None] = mapped_column(
        nullable=True,
        comment="Whether this loss could have been prevented",
    )
    lessons_learned: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Lessons learned from this loss",
    )

    # AI fields
    ai_analysis: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI-generated analysis of the loss",
    )
    ai_recommendations: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI recommendations to prevent similar losses",
    )

    # Metadata
    additional_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional structured data about the loss",
    )

    # Timestamps
    lost_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        comment="When the client was lost",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # Relationships
    client: Mapped["Client"] = relationship(
        "Client",
        foreign_keys=[client_id],
        lazy="selectin",
    )
    property: Mapped["Property | None"] = relationship(
        "Property",
        foreign_keys=[property_id],
        lazy="selectin",
    )
    broker: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[broker_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation of the ClientLoss."""
        return f"<ClientLoss(id={self.id}, client_id={self.client_id}, reason={self.loss_reason}, stage={self.loss_stage})>"

