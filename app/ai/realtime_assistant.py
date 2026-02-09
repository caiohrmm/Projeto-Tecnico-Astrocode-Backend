"""Real-time AI Assistant for attendances."""

import logging
import uuid
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DetectedInfo(BaseModel):
    """Information detected from attendance text."""
    
    field: str  # e.g., "budget_min", "city", "property_type"
    value: str
    confidence: float
    original_text: str  # The text that triggered detection


class PropertySuggestion(BaseModel):
    """Suggested property for the client."""
    
    property_id: str
    title: str
    city: str
    price: float
    property_type: str
    match_reason: str
    match_score: float  # 0-1


class SuggestedQuestion(BaseModel):
    """Suggested question for the attendant."""
    
    question: str
    reason: str
    priority: int  # 1 = high, 2 = medium, 3 = low
    category: str  # "qualification", "interest", "objection", "closing"


class RealTimeAnalysisResult(BaseModel):
    """Result of real-time attendance analysis."""
    
    # Detected information from the conversation
    detected_info: list[DetectedInfo] = Field(default_factory=list)
    
    # Property suggestions based on detected interests
    property_suggestions: list[PropertySuggestion] = Field(default_factory=list)
    
    # Suggested questions to ask
    suggested_questions: list[SuggestedQuestion] = Field(default_factory=list)
    
    # Alerts about important information
    alerts: list[str] = Field(default_factory=list)
    
    # Quick summary of what was detected
    summary: str = ""
    
    # Detected client intent
    detected_intent: str | None = None


class RealTimeAssistantService:
    """
    Real-time AI assistant for attendances.
    
    Provides:
    - Property suggestions based on conversation
    - Detection of important information (budget, location, preferences)
    - Suggested questions to qualify the lead
    - Alerts about opportunities or issues
    """

    def __init__(self):
        self.gemini = None

    def _get_gemini(self):
        """Lazy load Gemini service."""
        if self.gemini is None:
            from app.ai.gemini_service import GeminiService
            self.gemini = GeminiService()
        return self.gemini

    def analyze_text(
        self,
        text: str,
        client_name: str | None = None,
        client_budget_min: float | None = None,
        client_budget_max: float | None = None,
        client_city_interest: str | None = None,
        client_property_type: str | None = None,
        client_interest_type: str | None = None,
        available_properties: list[dict] | None = None,
    ) -> RealTimeAnalysisResult:
        """
        Analyze attendance text in real-time.
        
        Args:
            text: Current attendance text/notes
            client_name: Client's name for context
            client_budget_min: Known minimum budget
            client_budget_max: Known maximum budget
            client_city_interest: Known city of interest
            client_property_type: Known property type preference
            client_interest_type: Known interest type (BUY, RENT, etc.)
            available_properties: List of available properties to suggest from
            
        Returns:
            RealTimeAnalysisResult with suggestions and detections
        """
        if not text or len(text.strip()) < 10:
            return RealTimeAnalysisResult(
                summary="Aguardando mais informações..."
            )

        gemini = self._get_gemini()
        
        if not gemini.is_configured():
            return self._get_basic_analysis(text, available_properties)

        try:
            # Build context
            prompt = self._build_analysis_prompt(
                text=text,
                client_name=client_name,
                client_budget_min=client_budget_min,
                client_budget_max=client_budget_max,
                client_city_interest=client_city_interest,
                client_property_type=client_property_type,
                client_interest_type=client_interest_type,
            )
            
            result = gemini.chat(
                message=prompt,
                system_prompt=self._get_system_prompt(),
            )
            
            if result.get("answer"):
                analysis = self._parse_analysis_response(result["answer"])
                
                # Match properties if available
                if available_properties and analysis.detected_info:
                    analysis.property_suggestions = self._match_properties(
                        analysis.detected_info,
                        available_properties,
                        client_budget_min,
                        client_budget_max,
                    )
                
                return analysis
            
            return self._get_basic_analysis(text, available_properties)
            
        except Exception as e:
            logger.error(f"Error in real-time analysis: {e}")
            return self._get_basic_analysis(text, available_properties)

    def _get_system_prompt(self) -> str:
        """Get system prompt for real-time analysis."""
        return """Você é um assistente de IA para corretores de imóveis em tempo real.

Sua tarefa é analisar o texto de um atendimento em andamento e fornecer:
1. Informações detectadas (orçamento, cidade, tipo de imóvel, urgência)
2. Perguntas sugeridas para qualificar melhor o cliente
3. Alertas sobre oportunidades ou problemas

INFORMAÇÕES A DETECTAR:
- budget_min: Orçamento mínimo mencionado
- budget_max: Orçamento máximo mencionado  
- city: Cidade ou bairro de interesse
- property_type: Tipo de imóvel (casa, apartamento, terreno, comercial)
- interest_type: Interesse (comprar, alugar, vender, investir)
- urgency: Urgência (baixa, média, alta, imediata)
- bedrooms: Número de quartos desejados
- has_financing: Se menciona financiamento

CATEGORIAS DE PERGUNTAS:
- qualification: Qualificar o lead (orçamento, prazo)
- interest: Entender interesses específicos
- objection: Lidar com objeções
- closing: Perguntas para fechar negócio

Responda SEMPRE em JSON válido:
{
    "detected_info": [
        {"field": "campo", "value": "valor", "confidence": 0.9, "original_text": "trecho"}
    ],
    "suggested_questions": [
        {"question": "pergunta?", "reason": "motivo", "priority": 1, "category": "qualification"}
    ],
    "alerts": ["alerta 1", "alerta 2"],
    "summary": "resumo breve",
    "detected_intent": "SCHEDULE_VISIT" | "PRICE_NEGOTIATION" | "INFORMATION_REQUEST" | null
}"""

    def _build_analysis_prompt(
        self,
        text: str,
        client_name: str | None,
        client_budget_min: float | None,
        client_budget_max: float | None,
        client_city_interest: str | None,
        client_property_type: str | None,
        client_interest_type: str | None,
    ) -> str:
        """Build the analysis prompt."""
        prompt = f"""Analise este texto de atendimento imobiliário em tempo real:

TEXTO DO ATENDIMENTO:
\"\"\"{text}\"\"\"

"""
        
        # Add known client info for context
        known_info = []
        if client_name:
            known_info.append(f"- Nome: {client_name}")
        if client_budget_min or client_budget_max:
            known_info.append(f"- Orçamento conhecido: R$ {client_budget_min or 0:,.0f} - R$ {client_budget_max or 0:,.0f}")
        if client_city_interest:
            known_info.append(f"- Cidade de interesse: {client_city_interest}")
        if client_property_type:
            known_info.append(f"- Tipo de imóvel: {client_property_type}")
        if client_interest_type:
            known_info.append(f"- Interesse: {client_interest_type}")
        
        if known_info:
            prompt += "INFORMAÇÕES JÁ CONHECIDAS DO CLIENTE:\n" + "\n".join(known_info) + "\n\n"
        
        prompt += """Detecte NOVAS informações mencionadas no texto e sugira perguntas relevantes.
Foque em informações que ainda não conhecemos sobre o cliente.

Responda em JSON."""
        
        return prompt

    def _parse_analysis_response(self, response: str) -> RealTimeAnalysisResult:
        """Parse AI response into RealTimeAnalysisResult."""
        import json
        
        try:
            # Find JSON in response
            start = response.find("{")
            end = response.rfind("}") + 1
            
            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)
                
                # Parse detected info
                detected_info = []
                for info in data.get("detected_info", []):
                    detected_info.append(DetectedInfo(
                        field=info.get("field", "unknown"),
                        value=str(info.get("value", "")),
                        confidence=float(info.get("confidence", 0.5)),
                        original_text=info.get("original_text", ""),
                    ))
                
                # Parse suggested questions
                suggested_questions = []
                for q in data.get("suggested_questions", []):
                    suggested_questions.append(SuggestedQuestion(
                        question=q.get("question", ""),
                        reason=q.get("reason", ""),
                        priority=int(q.get("priority", 2)),
                        category=q.get("category", "qualification"),
                    ))
                
                return RealTimeAnalysisResult(
                    detected_info=detected_info,
                    suggested_questions=suggested_questions,
                    alerts=data.get("alerts", []),
                    summary=data.get("summary", ""),
                    detected_intent=data.get("detected_intent"),
                )
                
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse AI analysis response: {e}")
        
        return RealTimeAnalysisResult(summary="Análise não disponível")

    def _get_basic_analysis(
        self,
        text: str,
        available_properties: list[dict] | None,
    ) -> RealTimeAnalysisResult:
        """Get basic analysis without AI (keyword-based)."""
        text_lower = text.lower()
        
        detected_info = []
        alerts = []
        suggested_questions = []
        
        # Detect budget mentions
        import re
        budget_patterns = [
            r"r\$\s*([\d.,]+)",
            r"(\d{2,3})\s*mil",
            r"(\d{1,2})\s*milh",
        ]
        for pattern in budget_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                for match in matches:
                    detected_info.append(DetectedInfo(
                        field="budget",
                        value=match,
                        confidence=0.7,
                        original_text=match,
                    ))
        
        # Detect cities
        cities = ["são paulo", "rio de janeiro", "belo horizonte", "curitiba", "porto alegre", 
                  "brasília", "salvador", "fortaleza", "recife", "campinas"]
        for city in cities:
            if city in text_lower:
                detected_info.append(DetectedInfo(
                    field="city",
                    value=city.title(),
                    confidence=0.9,
                    original_text=city,
                ))
        
        # Detect property types
        property_keywords = {
            "casa": "HOUSE",
            "apartamento": "APARTMENT",
            "apto": "APARTMENT",
            "terreno": "LAND",
            "lote": "LAND",
            "comercial": "COMMERCIAL",
            "sala comercial": "COMMERCIAL",
            "fazenda": "RURAL",
            "sítio": "RURAL",
            "chácara": "RURAL",
        }
        for keyword, prop_type in property_keywords.items():
            if keyword in text_lower:
                detected_info.append(DetectedInfo(
                    field="property_type",
                    value=prop_type,
                    confidence=0.8,
                    original_text=keyword,
                ))
        
        # Detect urgency
        urgency_keywords = {
            "urgente": "HIGH",
            "preciso logo": "HIGH",
            "imediato": "IMMEDIATE",
            "o mais rápido": "HIGH",
            "sem pressa": "LOW",
            "pesquisando": "LOW",
        }
        for keyword, urgency in urgency_keywords.items():
            if keyword in text_lower:
                detected_info.append(DetectedInfo(
                    field="urgency",
                    value=urgency,
                    confidence=0.7,
                    original_text=keyword,
                ))
                if urgency in ["HIGH", "IMMEDIATE"]:
                    alerts.append(f"🔥 Cliente com urgência {urgency}!")
        
        # Detect financing
        if any(word in text_lower for word in ["financ", "parcela", "entrada", "caixa", "banco"]):
            detected_info.append(DetectedInfo(
                field="has_financing",
                value="true",
                confidence=0.7,
                original_text="financiamento mencionado",
            ))
            alerts.append("💰 Cliente mencionou financiamento")
        
        # Basic suggested questions
        if not any(d.field == "budget" for d in detected_info):
            suggested_questions.append(SuggestedQuestion(
                question="Qual é o seu orçamento para este imóvel?",
                reason="Orçamento não identificado",
                priority=1,
                category="qualification",
            ))
        
        if not any(d.field == "city" for d in detected_info):
            suggested_questions.append(SuggestedQuestion(
                question="Em qual cidade ou bairro você está buscando?",
                reason="Localização não identificada",
                priority=1,
                category="qualification",
            ))
        
        if not any(d.field == "property_type" for d in detected_info):
            suggested_questions.append(SuggestedQuestion(
                question="Você prefere casa ou apartamento?",
                reason="Tipo de imóvel não identificado",
                priority=2,
                category="interest",
            ))
        
        # Match properties if available
        property_suggestions = []
        if available_properties and detected_info:
            property_suggestions = self._match_properties(
                detected_info, available_properties, None, None
            )
        
        return RealTimeAnalysisResult(
            detected_info=detected_info,
            property_suggestions=property_suggestions,
            suggested_questions=suggested_questions,
            alerts=alerts,
            summary=f"Detectadas {len(detected_info)} informações" if detected_info else "Aguardando mais detalhes...",
        )

    def _match_properties(
        self,
        detected_info: list[DetectedInfo],
        available_properties: list[dict],
        known_budget_min: float | None,
        known_budget_max: float | None,
    ) -> list[PropertySuggestion]:
        """Match properties based on detected information."""
        suggestions = []
        
        # Extract detected values
        detected_city = None
        detected_type = None
        detected_budget = None
        
        for info in detected_info:
            if info.field == "city":
                detected_city = info.value.lower()
            elif info.field == "property_type":
                detected_type = info.value
            elif info.field in ["budget", "budget_max"]:
                try:
                    # Parse budget value
                    val = info.value.replace(".", "").replace(",", "")
                    if "mil" in info.original_text.lower():
                        detected_budget = float(val) * 1000
                    elif "milh" in info.original_text.lower():
                        detected_budget = float(val) * 1000000
                    else:
                        detected_budget = float(val)
                except ValueError:
                    pass
        
        # Use known budget if no new one detected
        if not detected_budget and known_budget_max:
            detected_budget = known_budget_max
        
        for prop in available_properties[:50]:  # Limit to 50 properties
            score = 0.0
            reasons = []
            
            prop_city = (prop.get("city") or "").lower()
            prop_type = prop.get("property_type")
            prop_price = prop.get("price") or prop.get("rent_price") or 0
            
            # City match
            if detected_city and detected_city in prop_city:
                score += 0.4
                reasons.append(f"Cidade: {prop.get('city')}")
            
            # Type match
            if detected_type and prop_type == detected_type:
                score += 0.3
                reasons.append(f"Tipo: {prop_type}")
            
            # Budget match (within 20% range)
            if detected_budget and prop_price:
                if prop_price <= detected_budget * 1.2:
                    score += 0.3
                    reasons.append("Dentro do orçamento")
                elif prop_price <= detected_budget * 1.5:
                    score += 0.1
                    reasons.append("Próximo do orçamento")
            
            if score >= 0.3:  # Minimum match threshold
                suggestions.append(PropertySuggestion(
                    property_id=str(prop.get("id", "")),
                    title=prop.get("title", "Imóvel"),
                    city=prop.get("city", ""),
                    price=prop_price,
                    property_type=prop_type or "UNKNOWN",
                    match_reason=", ".join(reasons),
                    match_score=min(1.0, score),
                ))
        
        # Sort by score and return top 5
        suggestions.sort(key=lambda x: x.match_score, reverse=True)
        return suggestions[:5]


# Singleton instance
realtime_assistant = RealTimeAssistantService()

