"""AI Journey Service for analyzing complete client journey and context."""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.ai.gemini_service import GeminiService
from app.ai.models import AISummary, Sentiment, DetectedIntent
from app.attendances.models import Attendance, AttendanceStatus
from app.clients.models import Client, ClientStatus, UrgencyLevel
from app.clients.timeline_models import ClientTimeline, TimelineEventType
from app.visits.models import Visit, VisitStatus
from app.properties.models import Property

logger = logging.getLogger(__name__)


class ClientJourneyService:
    """
    Service for analyzing complete client journey with AI.
    
    This service provides:
    - Complete context for AI analysis
    - Journey stage detection
    - Next action suggestions
    - Relationship health scoring
    - Pattern detection across interactions
    """
    
    _gemini_service: GeminiService | None = None
    
    @classmethod
    def _get_gemini_service(cls) -> GeminiService:
        """Get or create Gemini service instance."""
        if cls._gemini_service is None:
            cls._gemini_service = GeminiService()
        return cls._gemini_service
    
    @staticmethod
    def get_client_context(db: Session, client_id: uuid.UUID) -> dict[str, Any]:
        """
        Get complete client context for AI analysis.
        
        This compiles all relevant information about a client for AI processing:
        - Basic client info
        - All attendances with summaries
        - All visits
        - Timeline events
        - Derived insights
        
        Args:
            db: Database session
            client_id: Client UUID
            
        Returns:
            Complete context dictionary
        """
        # Get client
        client = db.get(Client, client_id)
        if not client:
            return {"error": "Client not found"}
        
        # Get all attendances
        attendances = list(db.scalars(
            select(Attendance)
            .where(Attendance.client_id == client_id)
            .order_by(Attendance.created_at.desc())
        ).all())
        
        # Get all AI summaries for this client
        ai_summaries = list(db.scalars(
            select(AISummary)
            .where(AISummary.client_id == client_id)
            .order_by(AISummary.created_at.desc())
        ).all())
        
        # Get all visits
        visits = list(db.scalars(
            select(Visit)
            .where(Visit.client_id == client_id)
            .order_by(Visit.scheduled_at.desc())
        ).all())
        
        # Get timeline events
        timeline = list(db.scalars(
            select(ClientTimeline)
            .where(ClientTimeline.client_id == client_id)
            .order_by(ClientTimeline.created_at.desc())
            .limit(50)
        ).all())
        
        # Get properties of interest (from visits and recommendations)
        property_ids = set()
        for visit in visits:
            if visit.property_id:
                property_ids.add(visit.property_id)
        for summary in ai_summaries:
            if summary.recommended_properties:
                property_ids.update(summary.recommended_properties)
        
        properties = []
        if property_ids:
            properties = list(db.scalars(
                select(Property)
                .where(Property.id.in_(property_ids))
            ).all())
        
        # Calculate derived insights
        insights = ClientJourneyService._calculate_insights(
            client, attendances, ai_summaries, visits
        )
        
        return {
            "client": {
                "id": str(client.id),
                "name": client.name,
                "phone": client.phone,
                "email": client.email,
                "lead_source": client.lead_source.value if client.lead_source else None,
                "current_status": client.current_status.value if client.current_status else None,
                "current_lead_score": client.current_lead_score,
                "current_urgency_level": client.current_urgency_level.value if client.current_urgency_level else None,
                "current_interest_type": client.current_interest_type.value if client.current_interest_type else None,
                "current_property_type": client.current_property_type.value if client.current_property_type else None,
                "current_budget_min": float(client.current_budget_min) if client.current_budget_min else None,
                "current_budget_max": float(client.current_budget_max) if client.current_budget_max else None,
                "current_city_interest": client.current_city_interest,
                "first_contact_at": client.first_contact_at.isoformat() if client.first_contact_at else None,
                "last_contact_at": client.last_contact_at.isoformat() if client.last_contact_at else None,
                "summary_notes": client.summary_notes,
                "created_at": client.created_at.isoformat(),
            },
            "attendances": [
                {
                    "id": str(a.id),
                    "status": a.status.value if a.status else None,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "updated_at": a.updated_at.isoformat() if a.updated_at else None,
                    "raw_content": a.raw_content,
                    "ai_summary": a.ai_summary,
                    "ai_next_steps": a.ai_next_steps,
                }
                for a in attendances
            ],
            "ai_summaries": [
                {
                    "id": str(s.id),
                    "attendance_id": str(s.attendance_id),
                    "summary_text": s.summary_text,
                    "detected_intent": s.detected_intent.value if s.detected_intent else None,
                    "interest_type_detected": s.interest_type_detected,
                    "budget_min_detected": s.budget_min_detected,
                    "budget_max_detected": s.budget_max_detected,
                    "urgency_level_detected": s.urgency_level_detected,
                    "lead_score_suggested": s.lead_score_suggested,
                    "sentiment": s.sentiment.value if s.sentiment else None,
                    "confidence_score": s.confidence_score,
                    "created_at": s.created_at.isoformat(),
                }
                for s in ai_summaries
            ],
            "visits": [
                {
                    "id": str(v.id),
                    "property_id": str(v.property_id) if v.property_id else None,
                    "status": v.status.value if v.status else None,
                    "scheduled_at": v.scheduled_at.isoformat() if v.scheduled_at else None,
                    "notes": v.notes,
                }
                for v in visits
            ],
            "properties_of_interest": [
                {
                    "id": str(p.id),
                    "title": p.title,
                    "city": p.city,
                    "property_type": p.property_type.value if p.property_type else None,
                    "price": float(p.price) if p.price else None,
                }
                for p in properties
            ],
            "timeline_summary": {
                "total_events": len(timeline),
                "recent_events": [
                    {
                        "event_type": t.event_type.value,
                        "title": t.title,
                        "created_at": t.created_at.isoformat(),
                    }
                    for t in timeline[:10]
                ],
            },
            "insights": insights,
        }
    
    @staticmethod
    def _calculate_insights(
        client: Client,
        attendances: list[Attendance],
        ai_summaries: list[AISummary],
        visits: list[Visit],
    ) -> dict[str, Any]:
        """Calculate derived insights from client data."""
        
        # Engagement metrics
        total_attendances = len(attendances)
        completed_attendances = len([a for a in attendances if a.status == AttendanceStatus.COMPLETED])
        total_visits = len(visits)
        completed_visits = len([v for v in visits if v.status == VisitStatus.COMPLETED])
        no_show_visits = len([v for v in visits if v.status == VisitStatus.NO_SHOW])
        
        # Sentiment trend
        sentiments = [s.sentiment for s in ai_summaries if s.sentiment]
        sentiment_trend = "UNKNOWN"
        if sentiments:
            positive = len([s for s in sentiments if s == Sentiment.POSITIVE])
            negative = len([s for s in sentiments if s == Sentiment.NEGATIVE])
            if positive > negative:
                sentiment_trend = "IMPROVING"
            elif negative > positive:
                sentiment_trend = "DECLINING"
            else:
                sentiment_trend = "STABLE"
        
        # Lead score trend
        lead_scores = [s.lead_score_suggested for s in ai_summaries if s.lead_score_suggested]
        lead_score_trend = "STABLE"
        if len(lead_scores) >= 2:
            if lead_scores[0] > lead_scores[-1]:
                lead_score_trend = "IMPROVING"
            elif lead_scores[0] < lead_scores[-1]:
                lead_score_trend = "DECLINING"
        
        # Average lead score from AI
        avg_ai_lead_score = sum(lead_scores) / len(lead_scores) if lead_scores else None
        
        # Days since last contact
        days_since_contact = None
        if client.last_contact_at:
            days_since_contact = (datetime.utcnow() - client.last_contact_at.replace(tzinfo=None)).days
        
        # Engagement score (0-100)
        engagement_score = 0
        if total_attendances > 0:
            engagement_score += min(total_attendances * 10, 30)
        if completed_visits > 0:
            engagement_score += min(completed_visits * 15, 30)
        if days_since_contact is not None and days_since_contact < 7:
            engagement_score += 20
        elif days_since_contact is not None and days_since_contact < 14:
            engagement_score += 10
        if no_show_visits > 0:
            engagement_score -= no_show_visits * 10
        engagement_score = max(0, min(100, engagement_score))
        
        # Detect intents across all summaries
        intents = [s.detected_intent for s in ai_summaries if s.detected_intent]
        most_common_intent = None
        if intents:
            from collections import Counter
            intent_counts = Counter(intents)
            most_common_intent = intent_counts.most_common(1)[0][0].value
        
        # Relationship health
        relationship_health = "UNKNOWN"
        if engagement_score >= 70 and sentiment_trend in ["IMPROVING", "STABLE"]:
            relationship_health = "EXCELLENT"
        elif engagement_score >= 50:
            relationship_health = "GOOD"
        elif engagement_score >= 30:
            relationship_health = "NEEDS_ATTENTION"
        elif engagement_score > 0:
            relationship_health = "AT_RISK"
        
        # Journey stage
        journey_stage = ClientJourneyService._detect_journey_stage(
            client, attendances, visits
        )
        
        return {
            "engagement_score": engagement_score,
            "relationship_health": relationship_health,
            "sentiment_trend": sentiment_trend,
            "lead_score_trend": lead_score_trend,
            "avg_ai_lead_score": avg_ai_lead_score,
            "days_since_contact": days_since_contact,
            "total_attendances": total_attendances,
            "completed_attendances": completed_attendances,
            "total_visits": total_visits,
            "completed_visits": completed_visits,
            "no_show_visits": no_show_visits,
            "most_common_intent": most_common_intent,
            "journey_stage": journey_stage,
        }
    
    @staticmethod
    def _detect_journey_stage(
        client: Client,
        attendances: list[Attendance],
        visits: list[Visit],
    ) -> str:
        """Detect the current stage in the client journey."""
        
        # Use client status if available
        if client.current_status:
            status = client.current_status
            if status == ClientStatus.WON:
                return "CLOSED_WON"
            elif status == ClientStatus.LOST:
                return "CLOSED_LOST"
            elif status == ClientStatus.NEGOTIATING:
                return "NEGOTIATING"
            elif status == ClientStatus.PROPOSAL_SENT:
                return "PROPOSAL"
            elif status in [ClientStatus.VISITING, ClientStatus.VISIT_SCHEDULED]:
                return "VISITING"
            elif status == ClientStatus.QUALIFIED:
                return "QUALIFIED"
            elif status == ClientStatus.CONTACTED:
                return "INITIAL_CONTACT"
            elif status == ClientStatus.NEW_LEAD:
                return "NEW_LEAD"
        
        # Infer from activity if no status
        completed_visits = len([v for v in visits if v.status == VisitStatus.COMPLETED])
        if completed_visits >= 3:
            return "DECISION_MAKING"
        elif completed_visits >= 1:
            return "VISITING"
        elif visits:
            return "QUALIFIED"
        elif len(attendances) >= 2:
            return "INITIAL_CONTACT"
        elif attendances:
            return "NEW_LEAD"
        
        return "UNKNOWN"
    
    @staticmethod
    def generate_next_actions(db: Session, client_id: uuid.UUID) -> list[dict[str, Any]]:
        """
        Generate AI-powered next action suggestions.
        
        Args:
            db: Database session
            client_id: Client UUID
            
        Returns:
            List of suggested next actions
        """
        context = ClientJourneyService.get_client_context(db, client_id)
        if "error" in context:
            return []
        
        insights = context["insights"]
        client = context["client"]
        
        actions = []
        
        # High priority: No contact in 7+ days for active lead
        if insights["days_since_contact"] and insights["days_since_contact"] >= 7:
            if insights["journey_stage"] not in ["CLOSED_WON", "CLOSED_LOST"]:
                actions.append({
                    "priority": "HIGH",
                    "action": "CONTACT",
                    "title": "Cliente sem contato há uma semana",
                    "description": f"Último contato há {insights['days_since_contact']} dias. Risco de perder o interesse.",
                    "suggested_channel": "WHATSAPP",
                })
        
        # Medium priority: Schedule visit after qualification
        if insights["journey_stage"] == "QUALIFIED" and insights["total_visits"] == 0:
            actions.append({
                "priority": "MEDIUM",
                "action": "SCHEDULE_VISIT",
                "title": "Agendar primeira visita",
                "description": "Cliente qualificado sem visitas agendadas. Sugerir visita a imóveis relevantes.",
                "suggested_channel": "WHATSAPP",
            })
        
        # Medium priority: Send proposal after visits
        if insights["completed_visits"] >= 2 and insights["journey_stage"] == "VISITING":
            actions.append({
                "priority": "MEDIUM",
                "action": "SEND_PROPOSAL",
                "title": "Enviar proposta",
                "description": f"Cliente realizou {insights['completed_visits']} visitas. Considerar enviar proposta.",
                "suggested_channel": "EMAIL",
            })
        
        # Low priority: Re-engage cold lead
        if insights["engagement_score"] < 30 and insights["journey_stage"] not in ["CLOSED_WON", "CLOSED_LOST"]:
            actions.append({
                "priority": "LOW",
                "action": "RE_ENGAGE",
                "title": "Reengajar lead frio",
                "description": "Engajamento baixo. Enviar conteúdo relevante ou novas opções de imóveis.",
                "suggested_channel": "WHATSAPP",
            })
        
        # Property recommendations
        if context["properties_of_interest"]:
            actions.append({
                "priority": "MEDIUM",
                "action": "RECOMMEND_PROPERTY",
                "title": "Apresentar imóveis recomendados",
                "description": f"IA identificou {len(context['properties_of_interest'])} imóveis compatíveis com o perfil.",
                "properties": [p["id"] for p in context["properties_of_interest"][:3]],
            })
        
        # Sort by priority
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        actions.sort(key=lambda x: priority_order.get(x["priority"], 99))
        
        return actions
    
    @staticmethod
    def generate_ai_journey_analysis(db: Session, client_id: uuid.UUID) -> dict[str, Any]:
        """
        Generate comprehensive AI analysis of client journey using Gemini.
        
        Args:
            db: Database session
            client_id: Client UUID
            
        Returns:
            AI-generated journey analysis
        """
        context = ClientJourneyService.get_client_context(db, client_id)
        if "error" in context:
            return {"error": context["error"]}
        
        gemini = ClientJourneyService._get_gemini_service()
        if not gemini.is_configured():
            return {
                "analysis": "Análise de IA não disponível. Configure a API do Gemini.",
                "next_actions": ClientJourneyService.generate_next_actions(db, client_id),
            }
        
        # Build prompt with context
        prompt = f"""Você é um consultor especializado em vendas imobiliárias. Analise a jornada completa deste cliente e forneça insights acionáveis.

## DADOS DO CLIENTE
- Nome: {context['client']['name']}
- Status: {context['client']['current_status'] or 'Não definido'}
- Interesse: {context['client']['current_interest_type'] or 'Não definido'}
- Tipo de imóvel: {context['client']['current_property_type'] or 'Não definido'}
- Cidade: {context['client']['current_city_interest'] or 'Não definida'}
- Orçamento: R$ {context['client']['current_budget_min'] or '?'} - R$ {context['client']['current_budget_max'] or '?'}
- Lead Score Atual: {context['client']['current_lead_score'] or 'Não calculado'}
- Urgência: {context['client']['current_urgency_level'] or 'Não definida'}

## MÉTRICAS DE ENGAJAMENTO
- Score de Engajamento: {context['insights']['engagement_score']}/100
- Saúde do Relacionamento: {context['insights']['relationship_health']}
- Tendência de Sentimento: {context['insights']['sentiment_trend']}
- Dias desde último contato: {context['insights']['days_since_contact'] or 'N/A'}
- Total de atendimentos: {context['insights']['total_attendances']}
- Visitas realizadas: {context['insights']['completed_visits']}

## HISTÓRICO DE ATENDIMENTOS
{chr(10).join([f"- [{a['created_at'][:10] if a['created_at'] else 'N/A'}] {a['ai_summary'] or a['raw_content'][:100]}" for a in context['attendances'][:5]])}

## RESUMOS DA IA
{chr(10).join([f"- Intenção: {s['detected_intent']}, Sentimento: {s['sentiment']}, Score: {s['lead_score_suggested']}" for s in context['ai_summaries'][:5]])}

## ANÁLISE SOLICITADA

Por favor, forneça:

1. **RESUMO DA JORNADA**: Descreva em 2-3 frases o perfil e momento atual do cliente.

2. **PROBABILIDADE DE CONVERSÃO**: Estime de 0-100% a chance de fechar negócio e explique brevemente.

3. **PONTOS DE ATENÇÃO**: Liste 2-3 pontos críticos que precisam de atenção.

4. **PRÓXIMOS PASSOS RECOMENDADOS**: Liste 3 ações específicas e prioritárias.

5. **ESTRATÉGIA DE ABORDAGEM**: Sugira a melhor forma de abordar este cliente no próximo contato.

Seja específico e objetivo. Respostas em português brasileiro."""

        try:
            result = gemini.chat(
                message=prompt,
                system_prompt="Você é um consultor especializado em vendas imobiliárias com foco em análise de clientes.",
            )
            
            if result.get("error"):
                logger.error(f"Error generating journey analysis: {result.get('error')}")
                return {
                    "analysis": "Erro ao gerar análise. Tente novamente.",
                    "next_actions": ClientJourneyService.generate_next_actions(db, client_id),
                }
            
            return {
                "analysis": result.get("answer", ""),
                "context_summary": {
                    "engagement_score": context["insights"]["engagement_score"],
                    "relationship_health": context["insights"]["relationship_health"],
                    "journey_stage": context["insights"]["journey_stage"],
                    "sentiment_trend": context["insights"]["sentiment_trend"],
                },
                "next_actions": ClientJourneyService.generate_next_actions(db, client_id),
            }
            
        except Exception as e:
            logger.error(f"Exception generating journey analysis: {e}", exc_info=True)
            return {
                "analysis": "Erro ao processar análise.",
                "next_actions": ClientJourneyService.generate_next_actions(db, client_id),
            }


class TimelineService:
    """Service for managing client timeline events."""
    
    @staticmethod
    def add_event(
        db: Session,
        client_id: uuid.UUID,
        event_type: TimelineEventType,
        title: str,
        description: str | None = None,
        event_data: dict[str, Any] | None = None,
        related_attendance_id: uuid.UUID | None = None,
        related_visit_id: uuid.UUID | None = None,
        related_property_id: uuid.UUID | None = None,
        created_by_id: uuid.UUID | None = None,
        ai_generated: bool = False,
        importance: int = 3,
    ) -> ClientTimeline:
        """
        Add a new event to the client timeline.
        
        Args:
            db: Database session
            client_id: Client UUID
            event_type: Type of event
            title: Short title
            description: Detailed description
            event_data: Event-specific data
            related_attendance_id: Related attendance
            related_visit_id: Related visit
            related_property_id: Related property
            created_by_id: User who triggered the event
            ai_generated: Whether AI generated this event
            importance: Importance level 1-5
            
        Returns:
            Created timeline event
        """
        event = ClientTimeline(
            client_id=client_id,
            event_type=event_type,
            title=title,
            description=description,
            event_data=event_data,
            related_attendance_id=related_attendance_id,
            related_visit_id=related_visit_id,
            related_property_id=related_property_id,
            created_by_id=created_by_id,
            ai_generated=ai_generated,
            importance=importance,
        )
        
        db.add(event)
        db.commit()
        db.refresh(event)
        
        return event
    
    @staticmethod
    def get_client_timeline(
        db: Session,
        client_id: uuid.UUID,
        limit: int = 50,
        event_types: list[TimelineEventType] | None = None,
    ) -> list[ClientTimeline]:
        """
        Get timeline events for a client.
        
        Args:
            db: Database session
            client_id: Client UUID
            limit: Maximum events to return
            event_types: Filter by event types
            
        Returns:
            List of timeline events
        """
        stmt = select(ClientTimeline).where(ClientTimeline.client_id == client_id)
        
        if event_types:
            stmt = stmt.where(ClientTimeline.event_type.in_(event_types))
        
        stmt = stmt.order_by(ClientTimeline.created_at.desc()).limit(limit)
        
        return list(db.scalars(stmt).all())

