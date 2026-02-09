"""Sale model for tracking closed deals."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.clients.models import Client
    from app.properties.models import Property
    from app.users.models import User


class SaleType(str, enum.Enum):
    """Enum for sale type."""

    SALE = "SALE"  # Venda
    RENT = "RENT"  # Aluguel


class SaleStatus(str, enum.Enum):
    """Enum for sale status."""

    PENDING = "PENDING"  # Aguardando documentação
    DOCUMENTATION = "DOCUMENTATION"  # Em análise de documentação
    CONTRACT = "CONTRACT"  # Contrato em elaboração
    SIGNED = "SIGNED"  # Contrato assinado
    COMPLETED = "COMPLETED"  # Venda/Aluguel concluído
    CANCELLED = "CANCELLED"  # Cancelado


class PaymentMethod(str, enum.Enum):
    """Enum for payment method."""

    CASH = "CASH"  # À vista
    FINANCING = "FINANCING"  # Financiamento
    INSTALLMENTS = "INSTALLMENTS"  # Parcelado direto
    MIXED = "MIXED"  # Misto (entrada + financiamento)


class Sale(Base):
    """
    Sale model representing closed deals (sales or rentals).

    This model tracks the complete lifecycle of a real estate transaction,
    from proposal accepted to deal completion.

    Attributes:
        id: Unique identifier (UUID)
        
        # Relationships
        client_id: Foreign key to Client
        property_id: Foreign key to Property
        broker_id: Foreign key to User (broker who closed the deal)
        
        # Sale Details
        sale_type: Type of transaction (SALE, RENT)
        status: Current status of the sale process
        
        # Financial
        sale_value: Total sale/rent value
        commission_percentage: Commission percentage for the broker
        commission_value: Calculated commission value
        down_payment: Down payment amount (if applicable)
        payment_method: Payment method used
        
        # Rent specific
        rent_duration_months: Duration of rent contract in months
        rent_start_date: Start date of rent contract
        
        # Timeline
        proposal_date: When the proposal was accepted
        contract_date: When the contract was signed
        completion_date: When the deal was completed
        
        # Notes and AI
        notes: Additional notes about the sale
        ai_analysis: AI-generated analysis of the sale
        ai_success_factors: AI-detected factors that led to success
        
        # Timestamps
        created_at: When the sale record was created
        updated_at: When the sale record was last updated
    """

    __tablename__ = "sales"

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
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Sale Details
    sale_type: Mapped[SaleType] = mapped_column(
        Enum(SaleType, native_enum=False, length=20),
        nullable=False,
        index=True,
    )
    status: Mapped[SaleStatus] = mapped_column(
        Enum(SaleStatus, native_enum=False, length=20),
        default=SaleStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Financial
    sale_value: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Total sale value or monthly rent value",
    )
    commission_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        default=Decimal("5.00"),
        comment="Commission percentage (default 5%)",
    )
    commission_value: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Calculated commission value",
    )
    down_payment: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Down payment amount",
    )
    payment_method: Mapped[PaymentMethod | None] = mapped_column(
        Enum(PaymentMethod, native_enum=False, length=20),
        nullable=True,
    )

    # Rent specific
    rent_duration_months: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Duration of rent contract in months",
    )
    rent_start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Timeline
    proposal_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the proposal was accepted",
    )
    contract_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the contract was signed",
    )
    completion_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the deal was completed",
    )

    # Notes and AI
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    ai_analysis: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI-generated analysis of the sale",
    )
    ai_success_factors: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI-detected factors that led to success",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
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
        """String representation of the Sale."""
        return f"<Sale(id={self.id}, client_id={self.client_id}, type={self.sale_type}, status={self.status}, value={self.sale_value})>"

