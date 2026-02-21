"""Repository for Loss database operations and AI analysis."""

import logging
import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients.models import Client, ClientStatus
from app.clients.repository import ClientRepository
from app.clients.timeline_models import ClientTimeline, TimelineEventType
from app.losses.models import ClientLoss, LossReason, LossStage
from app.losses.schemas import LossCreate, LossPatternAnalysis, LossStats, LossUpdate

logger = logging.getLogger(__name__)


class LossRepository:
    """Repository for Loss database operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, loss_data: LossCreate) -> ClientLoss:
        """
        Create a new loss record.

        This method:
        1. Creates the loss record
        2. Updates client status to LOST
        3. Adds timeline event
        4. Triggers AI analysis of this loss
        """
        # Create loss record
        db_loss = ClientLoss(
            client_id=loss_data.client_id,
            property_id=loss_data.property_id,
            broker_id=loss_data.broker_id,
            loss_reason=loss_data.loss_reason,
            loss_stage=loss_data.loss_stage,
            detailed_reason=loss_data.detailed_reason,
            client_feedback=loss_data.client_feedback,
            competitor_info=loss_data.competitor_info,
            could_have_been_prevented=loss_data.could_have_been_prevented,
            lessons_learned=loss_data.lessons_learned,
            lost_at=datetime.utcnow(),
        )
        self.db.add(db_loss)
        self.db.flush()

        # Update client status to LOST
        self._update_client_status(loss_data.client_id, ClientStatus.LOST)

        # ⚠️ IMPORTANT: Close active attendance when loss is registered
        # This ensures the attendance cycle is properly closed when user confirms the loss
        from app.attendances.repository import AttendanceRepository
        from app.attendances.models import AttendanceStatus
        
        attendance_repo = AttendanceRepository(self.db)
        active_attendance = attendance_repo.get_active_attendance_by_client(loss_data.client_id)
        
        if active_attendance:
            # Append finalization message to conversation log (perda registrada)
            attendance_repo.append_finalization_message(
                active_attendance,
                "Perda registrada. Ciclo encerrado como perdido.",
            )
            # Close the active attendance cycle
            active_attendance.status = AttendanceStatus.LOST
            self.db.flush()
            logger.info(f"Closed active attendance {active_attendance.id} when loss was registered for client {loss_data.client_id}")
            # Regenerate AI summary so it reflects "encerrado como perda"
            try:
                attendance_repo._generate_ai_summary(active_attendance)
                # Apply AI-suggested lead_score to client (e.g. reduced score for loss)
                attendance_repo.apply_closure_lead_score_to_client(active_attendance.id)
            except Exception as e:
                logger.warning(f"Could not regenerate AI summary after loss: {e}")

        # Add timeline event
        self._add_timeline_event(
            client_id=loss_data.client_id,
            event_type=TimelineEventType.STATUS_CHANGED,
            title="Cliente perdido",
            description=f"Motivo: {self._get_reason_label(loss_data.loss_reason)}. Estágio: {self._get_stage_label(loss_data.loss_stage)}",
            event_data={
                "loss_id": str(db_loss.id),
                "loss_reason": loss_data.loss_reason.value,
                "loss_stage": loss_data.loss_stage.value,
                "could_have_been_prevented": loss_data.could_have_been_prevented,
            },
            importance=4,
        )

        self.db.commit()
        self.db.refresh(db_loss)

        # Trigger AI analysis in background
        self._generate_loss_analysis(db_loss)

        return db_loss

    def get_by_id(self, loss_id: uuid.UUID) -> ClientLoss | None:
        """Get a loss by ID."""
        stmt = select(ClientLoss).where(ClientLoss.id == loss_id)
        return self.db.scalar(stmt)

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        client_id: uuid.UUID | None = None,
        broker_id: uuid.UUID | None = None,
        loss_reason: LossReason | None = None,
        loss_stage: LossStage | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> List[ClientLoss]:
        """Get all losses with optional filters."""
        stmt = select(ClientLoss)

        if client_id:
            stmt = stmt.where(ClientLoss.client_id == client_id)
        if broker_id:
            stmt = stmt.where(ClientLoss.broker_id == broker_id)
        if loss_reason:
            stmt = stmt.where(ClientLoss.loss_reason == loss_reason)
        if loss_stage:
            stmt = stmt.where(ClientLoss.loss_stage == loss_stage)
        if start_date:
            stmt = stmt.where(ClientLoss.lost_at >= start_date)
        if end_date:
            stmt = stmt.where(ClientLoss.lost_at <= end_date)

        stmt = stmt.order_by(ClientLoss.lost_at.desc()).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def update(self, loss: ClientLoss, loss_data: LossUpdate) -> ClientLoss:
        """Update a loss record."""
        update_dict = loss_data.model_dump(exclude_unset=True)

        for field, value in update_dict.items():
            setattr(loss, field, value)

        self.db.commit()
        self.db.refresh(loss)
        return loss

    def delete(self, loss: ClientLoss) -> None:
        """Delete a loss record."""
        self.db.delete(loss)
        self.db.commit()

    def get_stats(
        self,
        broker_id: uuid.UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> LossStats:
        """Get loss statistics."""
        stmt = select(ClientLoss)

        if broker_id:
            stmt = stmt.where(ClientLoss.broker_id == broker_id)
        if start_date:
            stmt = stmt.where(ClientLoss.lost_at >= start_date)
        if end_date:
            stmt = stmt.where(ClientLoss.lost_at <= end_date)

        losses = list(self.db.scalars(stmt).all())

        if not losses:
            return LossStats()

        # Count by reason
        reason_counts = Counter(l.loss_reason.value for l in losses)
        
        # Count by stage
        stage_counts = Counter(l.loss_stage.value for l in losses)
        
        # Count preventable
        preventable = sum(1 for l in losses if l.could_have_been_prevented is True)

        return LossStats(
            total_losses=len(losses),
            losses_by_reason=dict(reason_counts),
            losses_by_stage=dict(stage_counts),
            preventable_count=preventable,
        )

    def analyze_patterns(
        self,
        broker_id: uuid.UUID | None = None,
        days: int = 90,
    ) -> LossPatternAnalysis:
        """
        Analyze loss patterns using AI.

        This method:
        1. Collects loss data from the specified period
        2. Analyzes patterns
        3. Uses AI to generate insights and recommendations
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        losses = self.get_all(
            broker_id=broker_id,
            start_date=start_date,
            limit=500,
        )

        if not losses:
            return LossPatternAnalysis(
                total_losses=0,
                period_analyzed=f"Últimos {days} dias",
                summary="Nenhuma perda registrada no período analisado.",
            )

        # Calculate basic stats
        reason_counts = Counter(l.loss_reason.value for l in losses)
        stage_counts = Counter(l.loss_stage.value for l in losses)

        top_reasons = [
            {"reason": self._get_reason_label(LossReason(r)), "count": c, "percentage": round(c / len(losses) * 100, 1)}
            for r, c in reason_counts.most_common(5)
        ]

        critical_stages = [
            {"stage": self._get_stage_label(LossStage(s)), "count": c, "percentage": round(c / len(losses) * 100, 1)}
            for s, c in stage_counts.most_common(5)
        ]

        # Use AI for deeper analysis
        ai_insights = self._generate_pattern_analysis(losses, top_reasons, critical_stages)

        return LossPatternAnalysis(
            total_losses=len(losses),
            period_analyzed=f"Últimos {days} dias",
            top_reasons=top_reasons,
            critical_stages=critical_stages,
            patterns_detected=ai_insights.get("patterns", []),
            recommendations=ai_insights.get("recommendations", []),
            risk_factors=ai_insights.get("risk_factors", []),
            success_vs_loss_insights=ai_insights.get("comparison", ""),
            summary=ai_insights.get("summary", ""),
        )

    def _update_client_status(self, client_id: uuid.UUID, status: ClientStatus) -> None:
        """Update client status."""
        client_repo = ClientRepository(self.db)
        client = client_repo.get_by_id(client_id)
        if client:
            client.current_status = status
            self.db.flush()

    def _add_timeline_event(
        self,
        client_id: uuid.UUID,
        event_type: TimelineEventType,
        title: str,
        description: str | None = None,
        event_data: dict | None = None,
        importance: int = 3,
    ) -> None:
        """Add a timeline event for the client."""
        event = ClientTimeline(
            client_id=client_id,
            event_type=event_type,
            title=title,
            description=description,
            event_data=event_data,
            ai_generated=False,
            importance=importance,
        )
        self.db.add(event)
        self.db.flush()

    def _generate_loss_analysis(self, loss: ClientLoss) -> None:
        """Generate AI analysis for a single loss."""
        try:
            from app.ai.gemini_service import GeminiService

            gemini = GeminiService()
            if not gemini.is_configured():
                return

            client = loss.client
            
            prompt = f"""Analise esta perda de cliente imobiliário e forneça:
1. Uma análise breve do que pode ter acontecido
2. Recomendações específicas para evitar perdas similares

DADOS DA PERDA:
- Motivo principal: {self._get_reason_label(loss.loss_reason)}
- Estágio quando perdido: {self._get_stage_label(loss.loss_stage)}
- Detalhes: {loss.detailed_reason or 'Não informado'}
- Feedback do cliente: {loss.client_feedback or 'Não informado'}
- Informação sobre concorrente: {loss.competitor_info or 'Não informado'}

DADOS DO CLIENTE:
- Nome: {client.name if client else 'N/A'}
- Tipo de interesse: {client.current_interest_type.value if client and client.current_interest_type else 'N/A'}
- Orçamento: R$ {client.current_budget_min or 0:,.2f} - R$ {client.current_budget_max or 0:,.2f}
- Lead Score: {client.current_lead_score if client else 'N/A'}

Seja objetivo e prático nas recomendações."""

            result = gemini.chat(
                message=prompt,
                system_prompt="Você é um especialista em vendas imobiliárias e análise de negociações perdidas.",
            )

            if result.get("answer"):
                response = result["answer"]
                
                # Try to split analysis and recommendations
                loss.ai_analysis = response
                
                # Extract recommendations
                if "recomend" in response.lower():
                    idx = response.lower().find("recomend")
                    loss.ai_recommendations = response[idx:]
                
                self.db.flush()

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating AI analysis for loss {loss.id}: {e}")

    def _generate_pattern_analysis(
        self,
        losses: List[ClientLoss],
        top_reasons: List[dict],
        critical_stages: List[dict],
    ) -> dict:
        """Generate AI pattern analysis from loss data."""
        try:
            from app.ai.gemini_service import GeminiService

            gemini = GeminiService()
            if not gemini.is_configured():
                return self._get_default_analysis(losses, top_reasons)

            # Build context
            reasons_text = "\n".join([f"- {r['reason']}: {r['count']} ({r['percentage']}%)" for r in top_reasons])
            stages_text = "\n".join([f"- {s['stage']}: {s['count']} ({s['percentage']}%)" for s in critical_stages])
            
            # Sample of detailed reasons
            detailed_reasons = [l.detailed_reason for l in losses if l.detailed_reason][:10]
            feedbacks = [l.client_feedback for l in losses if l.client_feedback][:10]
            competitor_infos = [l.competitor_info for l in losses if l.competitor_info][:5]
            
            preventable_count = sum(1 for l in losses if l.could_have_been_prevented)
            preventable_pct = round(preventable_count / len(losses) * 100, 1) if losses else 0

            prompt = f"""Analise estes dados de clientes perdidos em uma imobiliária e forneça insights acionáveis:

RESUMO ({len(losses)} perdas analisadas):

PRINCIPAIS MOTIVOS:
{reasons_text}

ESTÁGIOS CRÍTICOS:
{stages_text}

PERDAS EVITÁVEIS: {preventable_count} ({preventable_pct}%)

DETALHES COLETADOS:
- Razões detalhadas: {'; '.join(detailed_reasons[:5]) if detailed_reasons else 'Não disponível'}
- Feedbacks de clientes: {'; '.join(feedbacks[:5]) if feedbacks else 'Não disponível'}
- Info de concorrentes: {'; '.join(competitor_infos[:3]) if competitor_infos else 'Não disponível'}

Forneça sua análise no seguinte formato JSON:
{{
    "patterns": ["padrão 1", "padrão 2", "padrão 3"],
    "recommendations": ["recomendação 1", "recomendação 2", "recomendação 3"],
    "risk_factors": ["fator de risco 1", "fator de risco 2"],
    "comparison": "Insight comparando vendas bem-sucedidas vs perdidas",
    "summary": "Resumo executivo em 2-3 frases"
}}

Seja específico e prático. Foque em ações que a equipe pode implementar imediatamente."""

            result = gemini.chat(
                message=prompt,
                system_prompt="Você é um consultor especialista em vendas imobiliárias e análise de dados comerciais. Responda sempre em JSON válido.",
            )

            if result.get("answer"):
                import json
                try:
                    # Try to extract JSON from response
                    response = result["answer"]
                    # Find JSON in response
                    start = response.find("{")
                    end = response.rfind("}") + 1
                    if start >= 0 and end > start:
                        json_str = response[start:end]
                        return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            return self._get_default_analysis(losses, top_reasons)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating pattern analysis: {e}")
            return self._get_default_analysis(losses, top_reasons)

    def _get_default_analysis(self, losses: List[ClientLoss], top_reasons: List[dict]) -> dict:
        """Get default analysis when AI is not available."""
        patterns = []
        recommendations = []
        
        if top_reasons:
            main_reason = top_reasons[0]
            patterns.append(f"{main_reason['reason']} é o motivo mais frequente ({main_reason['percentage']}%)")
            
            if main_reason['reason'] in ["Preço muito alto", "Orçamento insuficiente"]:
                recommendations.append("Qualificar melhor o orçamento dos leads antes de apresentar imóveis")
            elif main_reason['reason'] in ["Cliente não responde"]:
                recommendations.append("Implementar follow-up sistemático com múltiplos canais")

        preventable = sum(1 for l in losses if l.could_have_been_prevented)
        if preventable > len(losses) * 0.3:
            patterns.append(f"{round(preventable/len(losses)*100)}% das perdas eram evitáveis")
            recommendations.append("Revisar processos de atendimento e qualificação")

        return {
            "patterns": patterns,
            "recommendations": recommendations,
            "risk_factors": ["Alto tempo de resposta", "Falta de follow-up sistemático"],
            "comparison": "Análise comparativa requer mais dados de vendas bem-sucedidas.",
            "summary": f"Foram analisadas {len(losses)} perdas. O principal motivo foi '{top_reasons[0]['reason'] if top_reasons else 'não identificado'}'."
        }

    def _get_reason_label(self, reason: LossReason) -> str:
        """Get human-readable label for loss reason."""
        labels = {
            LossReason.PRICE_TOO_HIGH: "Preço muito alto",
            LossReason.BUDGET_INSUFFICIENT: "Orçamento insuficiente",
            LossReason.BETTER_OFFER_COMPETITOR: "Melhor oferta da concorrência",
            LossReason.PROPERTY_NOT_SUITABLE: "Imóvel não adequado",
            LossReason.LOCATION_NOT_IDEAL: "Localização não ideal",
            LossReason.NO_MATCHING_PROPERTY: "Nenhum imóvel compatível",
            LossReason.CLIENT_CHANGED_MIND: "Cliente mudou de ideia",
            LossReason.CLIENT_NOT_READY: "Cliente não está pronto",
            LossReason.CLIENT_UNRESPONSIVE: "Cliente não responde",
            LossReason.CLIENT_FINANCING_DENIED: "Financiamento negado",
            LossReason.SLOW_RESPONSE: "Resposta lenta",
            LossReason.POOR_SERVICE: "Atendimento ruim",
            LossReason.ECONOMIC_FACTORS: "Fatores econômicos",
            LossReason.PERSONAL_REASONS: "Motivos pessoais",
            LossReason.OTHER: "Outro motivo",
        }
        return labels.get(reason, reason.value)

    def _get_stage_label(self, stage: LossStage) -> str:
        """Get human-readable label for loss stage."""
        labels = {
            LossStage.INITIAL_CONTACT: "Contato inicial",
            LossStage.QUALIFICATION: "Qualificação",
            LossStage.VISIT_SCHEDULED: "Visita agendada",
            LossStage.VISIT_COMPLETED: "Visita realizada",
            LossStage.PROPOSAL: "Proposta",
            LossStage.NEGOTIATION: "Negociação",
            LossStage.CONTRACT: "Contrato",
        }
        return labels.get(stage, stage.value)

