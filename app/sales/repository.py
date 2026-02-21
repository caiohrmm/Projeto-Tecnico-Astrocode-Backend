"""Repository for Sale database operations."""

import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients.models import Client, ClientStatus, UrgencyLevel
from app.clients.repository import ClientRepository
from app.properties.models import Property, PropertyStatus
from app.properties.repository import PropertyRepository
from app.sales.models import Sale, SaleStatus, SaleType
from app.sales.schemas import SaleCreate, SaleStats, SaleUpdate
from app.clients.timeline_models import ClientTimeline, TimelineEventType

logger = logging.getLogger(__name__)


class SaleRepository:
    """Repository for Sale database operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, sale_data: SaleCreate) -> Sale:
        """
        Create a new sale record.

        This method:
        1. Creates the sale record
        2. Calculates commission value
        3. Updates client status to WON
        4. Updates property status to SOLD/RENTED
        5. Adds timeline event

        Args:
            sale_data: Sale creation data

        Returns:
            Created Sale instance
        """
        # Calculate commission value
        commission_value = None
        if sale_data.commission_percentage:
            commission_value = sale_data.sale_value * sale_data.commission_percentage / 100

        # Convert payment_methods to dict format for JSONB storage
        payment_methods_data = None
        if sale_data.payment_methods:
            payment_methods_data = [
                {
                    "method": item.method.value if hasattr(item.method, 'value') else str(item.method),
                    "value": float(item.value),
                    "description": item.description,
                }
                for item in sale_data.payment_methods
            ]
        
        # Create sale record
        db_sale = Sale(
            client_id=sale_data.client_id,
            property_id=sale_data.property_id,
            broker_id=sale_data.broker_id,
            sale_type=sale_data.sale_type,
            status=SaleStatus.PENDING,
            sale_value=sale_data.sale_value,
            commission_percentage=sale_data.commission_percentage,
            commission_value=commission_value,
            down_payment=sale_data.down_payment,
            payment_method=sale_data.payment_method,
            payment_methods=payment_methods_data,
            rent_duration_months=sale_data.rent_duration_months,
            rent_start_date=sale_data.rent_start_date,
            proposal_date=sale_data.proposal_date or datetime.utcnow(),
            notes=sale_data.notes,
        )
        self.db.add(db_sale)
        self.db.flush()

        # Update client status to WON
        self._update_client_status(sale_data.client_id, ClientStatus.WON)

        # Update property status
        if sale_data.property_id:
            new_status = PropertyStatus.SOLD if sale_data.sale_type == SaleType.SALE else PropertyStatus.RENTED
            self._update_property_status(sale_data.property_id, new_status)

        # ⚠️ IMPORTANT: Close active attendance when sale is registered
        # This ensures the attendance cycle is properly closed when user confirms the sale
        from app.attendances.repository import AttendanceRepository
        from app.attendances.models import AttendanceStatus

        attendance_repo = AttendanceRepository(self.db)
        active_attendance = attendance_repo.get_active_attendance_by_client(sale_data.client_id)
        
        if active_attendance:
            db_sale.attendance_id = active_attendance.id  # Vincular para sincronizar em cancelamento
            # Append finalization message to conversation log (venda registrada)
            attendance_repo.append_finalization_message(
                active_attendance,
                "Venda registrada. Ciclo encerrado como concluído (venda/aluguel).",
            )
            # Close the active attendance cycle
            active_attendance.status = AttendanceStatus.COMPLETED
            self.db.flush()
            logger.info(f"Closed active attendance {active_attendance.id} when sale was registered for client {sale_data.client_id}")
            # Regenerate AI summary so it reflects "concluído com venda" and the property purchased
            try:
                attendance_repo._generate_ai_summary(active_attendance)
                # Apply lead_score 100 (SALE_COMPLETED) to client so card shows 100, not old 40
                attendance_repo.apply_closure_lead_score_to_client(active_attendance.id)
            except Exception as e:
                logger.warning(f"Could not regenerate AI summary after sale: {e}")

        # Cliente sem atendimento ACTIVE → urgência baixa (ciclo encerrado com ganho)
        client_repo = ClientRepository(self.db)
        client = client_repo.get_by_id(sale_data.client_id)
        if client:
            client.current_urgency_level = UrgencyLevel.LOW
            self.db.flush()

        # Add timeline event
        self._add_timeline_event(
            client_id=sale_data.client_id,
            event_type=TimelineEventType.PROPOSAL_ACCEPTED,
            title="Proposta aceita - Venda iniciada" if sale_data.sale_type == SaleType.SALE else "Proposta aceita - Aluguel iniciado",
            description=f"Valor: R$ {sale_data.sale_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            related_property_id=sale_data.property_id,
            event_data={
                "sale_id": str(db_sale.id),
                "sale_type": sale_data.sale_type.value,
                "sale_value": float(sale_data.sale_value),
                "commission_percentage": float(sale_data.commission_percentage) if sale_data.commission_percentage else None,
            },
            importance=5,
        )

        self.db.commit()
        self.db.refresh(db_sale)
        return db_sale

    def get_by_id(self, sale_id: uuid.UUID) -> Sale | None:
        """Get a sale by ID."""
        stmt = select(Sale).where(Sale.id == sale_id)
        return self.db.scalar(stmt)

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        client_id: uuid.UUID | None = None,
        property_id: uuid.UUID | None = None,
        broker_id: uuid.UUID | None = None,
        sale_type: SaleType | None = None,
        status: SaleStatus | None = None,
    ) -> List[Sale]:
        """Get all sales with optional filters."""
        stmt = select(Sale)

        if client_id:
            stmt = stmt.where(Sale.client_id == client_id)
        if property_id:
            stmt = stmt.where(Sale.property_id == property_id)
        if broker_id:
            stmt = stmt.where(Sale.broker_id == broker_id)
        if sale_type:
            stmt = stmt.where(Sale.sale_type == sale_type)
        if status:
            stmt = stmt.where(Sale.status == status)

        stmt = stmt.order_by(Sale.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def update(self, sale: Sale, sale_data: SaleUpdate) -> Sale:
        """
        Update a sale record.

        Handles status transitions and triggers appropriate actions.
        """
        update_dict = sale_data.model_dump(exclude_unset=True)
        old_status = sale.status

        # Convert payment_methods to dict format for JSONB storage if present
        if "payment_methods" in update_dict and update_dict["payment_methods"] is not None:
            update_dict["payment_methods"] = [
                {
                    "method": item.method.value if hasattr(item.method, 'value') else str(item.method),
                    "value": float(item.value),
                    "description": item.description,
                }
                for item in update_dict["payment_methods"]
            ]

        for field, value in update_dict.items():
            setattr(sale, field, value)

        # Recalculate commission if value or percentage changed
        if "sale_value" in update_dict or "commission_percentage" in update_dict:
            if sale.commission_percentage and sale.sale_value:
                sale.commission_value = sale.sale_value * sale.commission_percentage / 100

        # Handle status transitions
        new_status = sale_data.status if sale_data.status else sale.status
        if new_status != old_status:
            self._handle_status_transition(sale, old_status, new_status)

        self.db.commit()
        self.db.refresh(sale)
        return sale

    def delete(self, sale: Sale) -> None:
        """Delete a sale record."""
        # Revert client status if needed
        if sale.status != SaleStatus.CANCELLED:
            self._update_client_status(sale.client_id, ClientStatus.NEGOTIATING)

        # Revert property status if needed
        if sale.property_id and sale.status != SaleStatus.CANCELLED:
            self._update_property_status(sale.property_id, PropertyStatus.PUBLISHED)

        self.db.delete(sale)
        self.db.commit()

    def get_stats(
        self,
        broker_id: uuid.UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> SaleStats:
        """Get sales statistics."""
        stmt = select(Sale)

        if broker_id:
            stmt = stmt.where(Sale.broker_id == broker_id)
        if start_date:
            stmt = stmt.where(Sale.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Sale.created_at <= end_date)

        sales = list(self.db.scalars(stmt).all())

        if not sales:
            return SaleStats()

        total_value = sum(s.sale_value for s in sales)
        total_commission = sum(s.commission_value or Decimal("0") for s in sales)
        
        completed_sales = [s for s in sales if s.status == SaleStatus.COMPLETED]
        pending_sales = [s for s in sales if s.status in [SaleStatus.PENDING, SaleStatus.DOCUMENTATION, SaleStatus.CONTRACT]]

        return SaleStats(
            total_sales=len(sales),
            total_value=total_value,
            total_commission=total_commission,
            sales_count=len([s for s in sales if s.sale_type == SaleType.SALE]),
            rent_count=len([s for s in sales if s.sale_type == SaleType.RENT]),
            pending_count=len(pending_sales),
            completed_count=len(completed_sales),
            avg_sale_value=total_value / len(sales) if sales else Decimal("0"),
            avg_commission=total_commission / len(sales) if sales else Decimal("0"),
        )

    def _handle_status_transition(
        self,
        sale: Sale,
        old_status: SaleStatus,
        new_status: SaleStatus,
    ) -> None:
        """Handle sale status transitions."""
        
        # When sale is completed
        if new_status == SaleStatus.COMPLETED and old_status != SaleStatus.COMPLETED:
            sale.completion_date = datetime.utcnow()
            
            # Add timeline event
            self._add_timeline_event(
                client_id=sale.client_id,
                event_type=TimelineEventType.SALE_COMPLETED,
                title="Venda concluída!" if sale.sale_type == SaleType.SALE else "Aluguel concluído!",
                description=f"Valor: R$ {sale.sale_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                related_property_id=sale.property_id,
                event_data={
                    "sale_id": str(sale.id),
                    "sale_type": sale.sale_type.value,
                    "sale_value": float(sale.sale_value),
                    "commission_value": float(sale.commission_value) if sale.commission_value else None,
                },
                importance=5,
            )

            # Trigger AI analysis
            self._generate_ai_analysis(sale)

        # When sale is signed (contract)
        elif new_status == SaleStatus.SIGNED and old_status != SaleStatus.SIGNED:
            sale.contract_date = datetime.utcnow()
            
            self._add_timeline_event(
                client_id=sale.client_id,
                event_type=TimelineEventType.CONTRACT_SIGNED,
                title="Contrato assinado",
                description="Contrato de compra e venda assinado" if sale.sale_type == SaleType.SALE else "Contrato de locação assinado",
                related_property_id=sale.property_id,
                importance=4,
            )

        # When sale is cancelled
        elif new_status == SaleStatus.CANCELLED and old_status != SaleStatus.CANCELLED:
            # Revert client status
            self._update_client_status(sale.client_id, ClientStatus.LOST)
            
            # Revert property status
            if sale.property_id:
                self._update_property_status(sale.property_id, PropertyStatus.PUBLISHED)
            
            self._add_timeline_event(
                client_id=sale.client_id,
                event_type=TimelineEventType.SALE_CANCELLED,
                title="Venda cancelada" if sale.sale_type == SaleType.SALE else "Aluguel cancelado",
                description=sale.notes or "Negociação não concluída",
                related_property_id=sale.property_id,
                importance=4,
            )

            # Registrar perda (gestor negou a venda) e sincronizar atendimento
            from app.losses.repository import LossRepository
            from app.losses.schemas import LossCreate
            from app.losses.models import LossReason, LossStage
            from app.attendances.repository import AttendanceRepository
            from app.attendances.models import Attendance, AttendanceStatus

            loss_repo = LossRepository(self.db)
            loss_repo.create(LossCreate(
                client_id=sale.client_id,
                property_id=sale.property_id,
                broker_id=sale.broker_id,
                loss_reason=LossReason.SALE_DENIED_BY_MANAGER,
                loss_stage=LossStage.CONTRACT,
                detailed_reason=sale.notes or "Venda negada pelo gestor. Negociação não concluída.",
            ))

            if sale.attendance_id:
                attendance = self.db.get(Attendance, sale.attendance_id)
                if attendance and attendance.status == AttendanceStatus.COMPLETED:
                    attendance_repo = AttendanceRepository(self.db)
                    attendance_repo.append_finalization_message(
                        attendance,
                        "Venda cancelada pelo gestor. Ciclo encerrado como perdido.",
                    )
                    attendance.status = AttendanceStatus.LOST
                    self.db.flush()
                    logger.info(
                        f"Updated attendance {attendance.id} to LOST after sale {sale.id} was cancelled"
                    )

    def _update_client_status(self, client_id: uuid.UUID, status: ClientStatus) -> None:
        """Update client status."""
        client_repo = ClientRepository(self.db)
        client = client_repo.get_by_id(client_id)
        if client:
            client.current_status = status
            self.db.flush()

    def _update_property_status(self, property_id: uuid.UUID, status: PropertyStatus) -> None:
        """Update property status."""
        property_repo = PropertyRepository(self.db)
        property_obj = property_repo.get_by_id(property_id)
        if property_obj:
            property_obj.status = status
            self.db.flush()

    def _add_timeline_event(
        self,
        client_id: uuid.UUID,
        event_type: TimelineEventType,
        title: str,
        description: str | None = None,
        related_property_id: uuid.UUID | None = None,
        event_data: dict | None = None,
        importance: int = 3,
    ) -> None:
        """Add a timeline event for the client."""
        event = ClientTimeline(
            client_id=client_id,
            event_type=event_type,
            title=title,
            description=description,
            related_property_id=related_property_id,
            event_data=event_data,
            ai_generated=False,
            importance=importance,
        )
        self.db.add(event)
        self.db.flush()

    def _generate_ai_analysis(self, sale: Sale) -> None:
        """Generate AI analysis for completed sale."""
        try:
            from app.ai.gemini_service import GeminiService
            
            gemini = GeminiService()
            if not gemini.is_configured():
                return

            # Build context for AI
            client = sale.client
            property_obj = sale.property

            prompt = f"""Analise esta venda imobiliária concluída e gere:
1. Um resumo da transação
2. Fatores de sucesso identificados
3. Aprendizados para futuras negociações

DADOS DA VENDA:
- Tipo: {"Venda" if sale.sale_type == SaleType.SALE else "Aluguel"}
- Valor: R$ {sale.sale_value:,.2f}
- Cliente: {client.name if client else "N/A"}
- Tempo até fechamento: {(sale.completion_date - sale.proposal_date).days if sale.completion_date and sale.proposal_date else "N/A"} dias

DADOS DO CLIENTE:
- Tipo de interesse original: {client.current_interest_type if client else "N/A"}
- Orçamento inicial: R$ {client.current_budget_min or 0:,.2f} - R$ {client.current_budget_max or 0:,.2f}
- Lead Score final: {client.current_lead_score if client else "N/A"}

DADOS DO IMÓVEL:
- Tipo: {property_obj.property_type.value if property_obj else "N/A"}
- Cidade: {property_obj.city if property_obj else "N/A"}
- Preço anunciado: R$ {property_obj.price or property_obj.rent_price or 0:,.2f}

Responda em português brasileiro, de forma profissional e concisa."""

            result = gemini.chat(
                message=prompt,
                system_prompt="Você é um especialista em análise de vendas imobiliárias.",
            )

            if result.get("answer"):
                # Parse response for analysis and success factors
                full_response = result["answer"]
                
                # Try to extract success factors
                success_factors = ""
                if "sucesso" in full_response.lower() or "fatores" in full_response.lower():
                    lines = full_response.split("\n")
                    in_factors = False
                    for line in lines:
                        if "fator" in line.lower() or "sucesso" in line.lower():
                            in_factors = True
                        if in_factors and line.strip():
                            success_factors += line + "\n"
                        if in_factors and not line.strip():
                            break

                sale.ai_analysis = full_response
                sale.ai_success_factors = success_factors if success_factors else None
                self.db.flush()

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating AI analysis for sale {sale.id}: {e}")

