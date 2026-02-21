"""AI Lead Classifier Service for initial lead scoring and classification."""

import logging
from typing import Optional
from pydantic import BaseModel

from app.clients.models import UrgencyLevel, InterestType, PropertyType, ClientStatus

logger = logging.getLogger(__name__)


class LeadClassification(BaseModel):
    """Schema for AI lead classification result."""
    
    lead_score: int  # 0-100
    urgency_level: UrgencyLevel
    interest_type: Optional[InterestType] = None
    property_type: Optional[PropertyType] = None
    suggested_status: ClientStatus = ClientStatus.NEW_LEAD
    
    # Extracted information
    budget_min: Optional[float] = None  # Minimum budget in BRL
    budget_max: Optional[float] = None  # Maximum budget in BRL
    city_interest: Optional[str] = None  # City where client wants property
    
    # AI reasoning
    classification_reason: str
    key_indicators: list[str]
    recommended_actions: list[str]
    
    # Confidence
    confidence: float  # 0-1


class LeadClassifierService:
    """
    Service for classifying leads using AI.
    
    Analyzes available information about a new lead and provides:
    - Initial lead score (0-100)
    - Urgency level assessment
    - Interest type detection
    - Property type preferences
    - Recommended next actions
    """

    def __init__(self):
        self.gemini = None

    def _get_gemini(self):
        """Lazy load Gemini service."""
        if self.gemini is None:
            from app.ai.gemini_service import GeminiService
            self.gemini = GeminiService()
        return self.gemini

    @staticmethod
    def _is_time_or_period_expression(text: str) -> bool:
        """Return True if text looks like time/period (e.g. 'parte da tarde'), not a city name."""
        if not text or len(text) < 3:
            return False
        lower = text.strip().lower()
        time_words = {
            "parte", "tarde", "manhã", "manha", "noite", "madrugada",
            "horário", "horario", "período", "periodo", "turno",
            "dia", "hora", "horas", "segunda", "terça", "quarta", "quinta", "sexta", "sábado", "sabado", "domingo",
        }
        words = set(lower.split())
        return bool(words & time_words)

    def classify_lead(
        self,
        name: str,
        phone: str,
        email: Optional[str] = None,
        lead_source: str = "WHATSAPP",
        initial_message: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> LeadClassification:
        """
        Classify a new lead based on available information.
        
        Args:
            name: Lead's name
            phone: Lead's phone number
            email: Lead's email (optional)
            lead_source: Source of the lead (WHATSAPP, SITE, PHONE)
            initial_message: First message from the lead (optional)
            notes: Any additional notes (optional)
            
        Returns:
            LeadClassification with scores and recommendations
        """
        gemini = self._get_gemini()
        
        if not gemini.is_configured():
            return self._get_default_classification(lead_source)
        
        try:
            # Build context for AI
            prompt = self._build_classification_prompt(
                name=name,
                phone=phone,
                email=email,
                lead_source=lead_source,
                initial_message=initial_message,
                notes=notes,
            )
            
            result = gemini.chat(
                message=prompt,
                system_prompt=self._get_system_prompt(),
            )
            
            if result.get("answer"):
                return self._parse_classification_response(result["answer"], lead_source)
            
            return self._get_default_classification(lead_source)
            
        except Exception as e:
            logger.error(f"Error classifying lead: {e}")
            return self._get_default_classification(lead_source)

    def reclassify_lead(
        self,
        name: str,
        phone: str,
        email: Optional[str] = None,
        lead_source: str = "WHATSAPP",
        current_status: Optional[str] = None,
        attendances_count: int = 0,
        visits_count: int = 0,
        days_since_first_contact: int = 0,
        last_attendance_summary: Optional[str] = None,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        city_interest: Optional[str] = None,
    ) -> LeadClassification:
        """
        Reclassify an existing lead based on interaction history.
        
        This is useful for periodic re-evaluation of leads.
        """
        gemini = self._get_gemini()
        
        if not gemini.is_configured():
            return self._get_default_classification(lead_source)
        
        try:
            prompt = f"""Reclassifique este lead imobiliário baseado no histórico de interações:

DADOS DO LEAD:
- Nome: {name}
- Telefone: {phone}
- Email: {email or 'Não informado'}
- Origem: {self._get_source_label(lead_source)}
- Status atual: {current_status or 'Novo'}

HISTÓRICO:
- Atendimentos realizados: {attendances_count}
- Visitas realizadas: {visits_count}
- Dias desde primeiro contato: {days_since_first_contact}
- Último resumo de atendimento: {last_attendance_summary or 'Não disponível'}

PREFERÊNCIAS CONHECIDAS:
- Orçamento: R$ {budget_min or 0:,.0f} - R$ {budget_max or 0:,.0f}
- Cidade de interesse: {city_interest or 'Não informada'}

Forneça a classificação no formato JSON especificado."""

            result = gemini.chat(
                message=prompt,
                system_prompt=self._get_system_prompt(),
            )
            
            if result.get("answer"):
                return self._parse_classification_response(result["answer"], lead_source)
            
            return self._get_default_classification(lead_source)
            
        except Exception as e:
            logger.error(f"Error reclassifying lead: {e}")
            return self._get_default_classification(lead_source)

    def _get_system_prompt(self) -> str:
        """Get system prompt for lead classification."""
        return """Você é um especialista em qualificação de leads para o mercado imobiliário brasileiro.

Sua tarefa é analisar as informações disponíveis de um novo lead e classificá-lo.

CRITÉRIOS DE LEAD SCORE (0-100):
- 0-25: Lead frio (apenas curioso, sem intenção clara)
- 26-50: Lead morno (interesse inicial, precisa ser qualificado)
- 51-75: Lead quente (interesse claro, orçamento definido)
- 76-100: Lead muito quente (pronto para comprar/alugar)

INDICADORES DE URGÊNCIA:
- LOW: Sem prazo definido, apenas pesquisando
- MEDIUM: Pretende decidir nos próximos 3-6 meses
- HIGH: Pretende decidir no próximo mês
- IMMEDIATE: Precisa de imóvel urgentemente

TIPOS DE INTERESSE:
- BUY: Quer comprar
- RENT: Quer alugar
- SELL: Quer vender
- INVEST: Quer investir

TIPOS DE IMÓVEL:
- HOUSE: Casa
- APARTMENT: Apartamento
- LAND: Terreno
- COMMERCIAL: Comercial
- RURAL: Rural

IMPORTANTE - EXTRAÇÃO DE DADOS:
- Se a mensagem mencionar orçamento/preço, extraia os valores em reais (R$) e retorne em "budget_min" e "budget_max"
- Se mencionar localização/cidade (nome de lugar), extraia o nome da cidade e retorne em "city_interest"
- NUNCA use city_interest para horário ou período: "parte da tarde", "de manhã", "à noite", "turno da manhã" NÃO são cidades — city_interest é APENAS localização geográfica (nome de cidade/bairro/região).
- Exemplos de orçamento: "500 mil" = 500000, "600.000" = 600000, "entre 500 e 600 mil" = budget_min: 500000, budget_max: 600000
- Exemplos de cidade: "São Paulo", "Rio de Janeiro", "centro de São Paulo" = "São Paulo". Se só mencionar "visita na parte da tarde", deixe city_interest como null.

STATUS SUGERIDO (suggested_status):
Baseado no lead_score, urgência e informações disponíveis, sugira o status inicial mais apropriado:
- NEW_LEAD: Lead frio (score 0-25), sem informações claras
- CONTACTED: Lead já foi contatado ou tem informações básicas (score 26-40)
- QUALIFIED: Lead quente com interesse claro, orçamento definido, urgência média/alta (score 51-75)
- QUALIFIED: Lead muito quente com todas informações, urgência alta/imediata, pré-aprovação (score 76-100)
- Use QUALIFIED quando: orçamento definido + tipo de imóvel + localização + urgência MEDIUM/HIGH/IMMEDIATE
- Use CONTACTED quando: tem mensagem inicial detalhada mas falta alguma informação importante
- Use NEW_LEAD apenas quando: informações muito limitadas, apenas dados básicos

Responda SEMPRE em JSON válido no formato:
{
    "lead_score": número de 0-100,
    "urgency_level": "LOW" | "MEDIUM" | "HIGH" | "IMMEDIATE",
    "interest_type": "BUY" | "RENT" | "SELL" | "INVEST" | null,
    "property_type": "HOUSE" | "APARTMENT" | "LAND" | "COMMERCIAL" | "RURAL" | null,
    "budget_min": número em reais ou null,
    "budget_max": número em reais ou null,
    "city_interest": "nome da cidade" ou null,
    "suggested_status": "NEW_LEAD" | "CONTACTED" | "QUALIFIED" | "VISIT_SCHEDULED" | "VISITING" | "PROPOSAL_SENT" | "NEGOTIATING" | "WON" | "LOST" | "INACTIVE",
    "classification_reason": "Explicação breve da classificação",
    "key_indicators": ["indicador 1", "indicador 2"],
    "recommended_actions": ["ação 1", "ação 2"],
    "confidence": número de 0 a 1
}"""

    def _build_classification_prompt(
        self,
        name: str,
        phone: str,
        email: Optional[str],
        lead_source: str,
        initial_message: Optional[str],
        notes: Optional[str],
    ) -> str:
        """Build the classification prompt."""
        source_label = self._get_source_label(lead_source)
        
        prompt = f"""Classifique este novo lead imobiliário:

DADOS DO LEAD:
- Nome: {name}
- Telefone: {phone}
- Email: {email or 'Não informado'}
- Origem: {source_label}
"""

        if initial_message:
            prompt += f"\nMENSAGEM INICIAL DO CLIENTE:\n\"{initial_message}\"\n"
        
        if notes:
            prompt += f"\nOBSERVAÇÕES ADICIONAIS:\n{notes}\n"
        
        if not initial_message and not notes:
            prompt += "\n(Nenhuma mensagem ou observação disponível - classifique baseado apenas nos dados básicos)\n"
        
        prompt += "\nForneça a classificação no formato JSON especificado."
        
        return prompt

    def _get_source_label(self, lead_source: str) -> str:
        """Get human-readable label for lead source."""
        labels = {
            "WHATSAPP": "WhatsApp",
            "SITE": "Site/Portal",
            "PHONE": "Telefone",
        }
        return labels.get(lead_source, lead_source)

    def _parse_classification_response(self, response: str, lead_source: str) -> LeadClassification:
        """Parse AI response into LeadClassification."""
        import json
        
        try:
            # Find JSON in response
            start = response.find("{")
            end = response.rfind("}") + 1
            
            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)
                
                # Parse urgency level
                urgency_map = {
                    "LOW": UrgencyLevel.LOW,
                    "MEDIUM": UrgencyLevel.MEDIUM,
                    "HIGH": UrgencyLevel.HIGH,
                    "IMMEDIATE": UrgencyLevel.IMMEDIATE,
                }
                urgency = urgency_map.get(data.get("urgency_level", "MEDIUM"), UrgencyLevel.MEDIUM)
                
                # Parse interest type
                interest_type = None
                if data.get("interest_type"):
                    interest_map = {
                        "BUY": InterestType.BUY,
                        "RENT": InterestType.RENT,
                        "SELL": InterestType.SELL,
                        "INVEST": InterestType.INVEST,
                    }
                    interest_type = interest_map.get(data["interest_type"])
                
                # Parse property type
                property_type = None
                if data.get("property_type"):
                    property_map = {
                        "HOUSE": PropertyType.HOUSE,
                        "APARTMENT": PropertyType.APARTMENT,
                        "LAND": PropertyType.LAND,
                        "COMMERCIAL": PropertyType.COMMERCIAL,
                        "RURAL": PropertyType.RURAL,
                    }
                    property_type = property_map.get(data["property_type"])
                
                # Extract budget and city
                budget_min = data.get("budget_min")
                budget_max = data.get("budget_max")
                city_interest = data.get("city_interest")
                # Reject time/period expressions mistaken as city (e.g. "Parte da Tarde")
                if city_interest and self._is_time_or_period_expression(city_interest):
                    city_interest = None
                
                # Convert budget to float if provided
                if budget_min is not None:
                    try:
                        budget_min = float(budget_min)
                    except (ValueError, TypeError):
                        budget_min = None
                
                if budget_max is not None:
                    try:
                        budget_max = float(budget_max)
                    except (ValueError, TypeError):
                        budget_max = None
                
                # Parse suggested_status
                suggested_status = ClientStatus.NEW_LEAD  # Default
                if data.get("suggested_status"):
                    status_map = {
                        "NEW_LEAD": ClientStatus.NEW_LEAD,
                        "CONTACTED": ClientStatus.CONTACTED,
                        "QUALIFIED": ClientStatus.QUALIFIED,
                        "VISIT_SCHEDULED": ClientStatus.VISIT_SCHEDULED,
                        "VISITING": ClientStatus.VISITING,
                        "PROPOSAL_SENT": ClientStatus.PROPOSAL_SENT,
                        "NEGOTIATING": ClientStatus.NEGOTIATING,
                        "WON": ClientStatus.WON,
                        "LOST": ClientStatus.LOST,
                        "INACTIVE": ClientStatus.INACTIVE,
                    }
                    suggested_status = status_map.get(data["suggested_status"], ClientStatus.NEW_LEAD)
                else:
                    # Auto-determine status based on lead_score and urgency if not provided
                    lead_score = min(100, max(0, int(data.get("lead_score", 30))))
                    if lead_score >= 76 or urgency == UrgencyLevel.IMMEDIATE:
                        suggested_status = ClientStatus.QUALIFIED
                    elif lead_score >= 51 or urgency == UrgencyLevel.HIGH:
                        suggested_status = ClientStatus.QUALIFIED
                    elif lead_score >= 26 or urgency == UrgencyLevel.MEDIUM:
                        suggested_status = ClientStatus.CONTACTED
                
                return LeadClassification(
                    lead_score=min(100, max(0, int(data.get("lead_score", 30)))),
                    urgency_level=urgency,
                    interest_type=interest_type,
                    property_type=property_type,
                    suggested_status=suggested_status,
                    budget_min=budget_min,
                    budget_max=budget_max,
                    city_interest=city_interest,
                    classification_reason=data.get("classification_reason", "Classificação automática"),
                    key_indicators=data.get("key_indicators", []),
                    recommended_actions=data.get("recommended_actions", []),
                    confidence=min(1.0, max(0.0, float(data.get("confidence", 0.5)))),
                )
                
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse AI classification response: {e}")
        
        return self._get_default_classification(lead_source)

    def _get_default_classification(self, lead_source: str) -> LeadClassification:
        """Get default classification when AI is not available."""
        # Higher score for proactive sources
        base_scores = {
            "WHATSAPP": 35,
            "SITE": 30,
            "PHONE": 40,
        }
        
        return LeadClassification(
            lead_score=base_scores.get(lead_source, 30),
            urgency_level=UrgencyLevel.MEDIUM,
            interest_type=None,
            property_type=None,
            suggested_status=ClientStatus.NEW_LEAD,
            classification_reason=f"Lead recebido via {self._get_source_label(lead_source)}. Classificação padrão aplicada.",
            key_indicators=[
                f"Origem: {self._get_source_label(lead_source)}",
                "Dados básicos cadastrados",
            ],
            recommended_actions=[
                "Realizar primeiro contato em até 24h",
                "Qualificar interesse e orçamento",
                "Identificar tipo de imóvel desejado",
            ],
            confidence=0.3,
        )


# Singleton instance
lead_classifier = LeadClassifierService()

