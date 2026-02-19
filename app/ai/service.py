"""AI service for generating summaries from attendances."""

import json
import logging
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.ai.gemini_service import GeminiService
from app.ai.models import (
    AISummary,
    AISummaryStatus,
    DetectedIntent,
    Sentiment,
)
from app.attendances.models import Attendance
from app.clients.models import InterestType, PropertyType, UrgencyLevel
from app.properties.models import PropertyType as PropertyTypeEnum
from app.properties.repository import PropertyRepository

logger = logging.getLogger(__name__)


class AISummaryService:
    """Service for generating AI summaries from attendances."""

    # Current prompt version
    PROMPT_VERSION = "2.0.0"
    MODEL_USED = "gemini-2.5-flash"
    
    # Gemini service instance
    _gemini_service: GeminiService | None = None
    
    @classmethod
    def _get_gemini_service(cls) -> GeminiService:
        """Get or create Gemini service instance."""
        if cls._gemini_service is None:
            cls._gemini_service = GeminiService()
        return cls._gemini_service

    @staticmethod
    def generate_summary(
        attendance: Attendance,
        db: Session | None = None,
    ) -> dict[str, Any]:
        """
        Generate AI summary from attendance raw content.

        This is a mock implementation that simulates AI analysis.
        In production, this would call an actual AI API (OpenAI, Anthropic, etc.).

        Args:
            attendance: Attendance instance to analyze

        Returns:
            Dictionary with all AI-generated fields for AISummary
        """
        try:
            raw_content = attendance.raw_content.lower()

            # Detect urgency FIRST, before generating summary, to ensure consistency
            urgency_level = AISummaryService._detect_urgency(attendance.raw_content)
            
            # Generate AI summary using Gemini API, passing detected urgency for consistency
            summary_text = AISummaryService._generate_summary_text(
                attendance.raw_content, 
                detected_urgency=urgency_level
            )
            key_points = AISummaryService._extract_key_points(raw_content)
            detected_intent = AISummaryService._detect_intent(raw_content)
            interest_type = AISummaryService._detect_interest_type(raw_content)
            budget_range = AISummaryService._detect_budget(raw_content)
            lead_score = AISummaryService._suggest_lead_score(
                interest_type,
                urgency_level,
                budget_range,
                detected_intent,
            )
            sentiment = AISummaryService._detect_sentiment(raw_content)
            confidence_score = AISummaryService._calculate_confidence(
                raw_content,
                interest_type,
                budget_range,
            )

            # Extract city from raw content and add to key_points
            # Note: use original content (not lowercased) for city extraction
            city = AISummaryService._extract_city(attendance.raw_content)
            if city and key_points:
                key_points["city"] = city
            
            # Extract property type from raw content and add to key_points
            detected_property_type = AISummaryService._extract_property_type(attendance.raw_content)
            if detected_property_type and key_points:
                key_points["property_type"] = detected_property_type.value

            # Generate property recommendations ONLY if no specific property is already assigned
            # If client has a specific property interest (property_id), don't recommend others
            recommended_properties: list[uuid.UUID] | None = None
            if db and not attendance.property_id and (interest_type or city or detected_property_type or budget_range.get("min") or budget_range.get("max")):
                recommended_properties = AISummaryService._recommend_properties(
                    db=db,
                    client_id=attendance.client_id,
                    interest_type=interest_type.value if interest_type else None,
                    property_type=detected_property_type.value if detected_property_type else None,
                    city=city,
                    budget_min=budget_range.get("min"),
                    budget_max=budget_range.get("max"),
                )

            return {
                "summary_text": summary_text,
                "key_points": key_points,
                "detected_intent": detected_intent,
                "interest_type_detected": interest_type,
                "budget_min_detected": budget_range.get("min"),
                "budget_max_detected": budget_range.get("max"),
                "urgency_level_detected": urgency_level,
                "lead_score_suggested": lead_score,
                "sentiment": sentiment,
                "recommended_properties": recommended_properties,
                "model_used": AISummaryService.MODEL_USED,
                "prompt_version": AISummaryService.PROMPT_VERSION,
                "confidence_score": confidence_score,
                "status": AISummaryStatus.COMPLETED,
            }
        except Exception as e:
            logger.error(f"Error generating AI summary for attendance {attendance.id}: {e}")
            return {
                "summary_text": f"Error processing attendance: {str(e)}",
                "key_points": None,
                "detected_intent": None,
                "interest_type_detected": None,
                "budget_min_detected": None,
                "budget_max_detected": None,
                "urgency_level_detected": None,
                "lead_score_suggested": None,
                "sentiment": None,
                "model_used": AISummaryService.MODEL_USED,
                "prompt_version": AISummaryService.PROMPT_VERSION,
                "confidence_score": 0.0,
                "status": AISummaryStatus.FAILED,
                "error_message": str(e),
            }

    @staticmethod
    def _truncate_content_intelligently(content: str, max_chars: int = 50000) -> str:
        """
        Truncate content intelligently, keeping the most recent and relevant parts.
        
        Strategy:
        - If content is within limit, return as-is
        - If exceeds limit, keep:
          1. First 20% (context/objective)
          2. Last 80% (most recent conversations)
        
        This ensures we maintain context while prioritizing recent information.
        
        Args:
            content: Raw content to truncate
            max_chars: Maximum characters to keep (default 50k for AI processing)
            
        Returns:
            Truncated content
        """
        if len(content) <= max_chars:
            return content
        
        logger.warning(
            f"Content exceeds {max_chars} chars ({len(content)}). "
            "Truncating intelligently to maintain context."
        )
        
        # Keep first 20% for context (objective, initial conversation)
        first_part_size = int(max_chars * 0.2)
        first_part = content[:first_part_size]
        
        # Keep last 80% for recent conversations
        last_part_size = max_chars - first_part_size
        last_part = content[-last_part_size:]
        
        # Combine with separator
        truncated = f"{first_part}\n\n[... conteúdo intermediário removido para otimização ...]\n\n{last_part}"
        
        return truncated
    
    @staticmethod
    def _generate_summary_text(raw_content: str, detected_urgency: UrgencyLevel | None = None) -> str:
        """
        Generate summary text from raw content using Gemini API.
        
        Automatically truncates content if it exceeds 50k characters to:
        - Avoid excessive API costs
        - Maintain AI context window
        - Prioritize recent conversations while keeping initial context
        
        Args:
            raw_content: Raw content of the attendance
            detected_urgency: Detected urgency level to ensure consistency in summary
        """
        gemini = AISummaryService._get_gemini_service()
        
        # Truncate content intelligently if too large (50k chars limit for AI processing)
        # This prevents excessive API costs and maintains context window
        processed_content = AISummaryService._truncate_content_intelligently(raw_content, max_chars=50000)
        
        # If Gemini is not configured, fallback to simple extraction
        if not gemini.is_configured():
            logger.warning("Gemini API not configured, using fallback summary generation")
            sentences = processed_content.split(".")
            important_sentences = [s.strip() for s in sentences if len(s.strip()) > 20][:3]
            summary = ". ".join(important_sentences)
            return summary if summary else processed_content[:200]
        
        # Use Gemini to generate a real summary
        from datetime import datetime
        
        # Get current date context for the AI
        current_date = datetime.now().strftime("%d/%m/%Y")
        
        # Map urgency level to Portuguese description for the prompt
        urgency_context = ""
        if detected_urgency:
            urgency_map = {
                UrgencyLevel.IMMEDIATE: "URGENTE/Imediata",
                UrgencyLevel.HIGH: "ALTA",
                UrgencyLevel.MEDIUM: "MÉDIA",
                UrgencyLevel.LOW: "BAIXA",
            }
            urgency_label = urgency_map.get(detected_urgency, "MÉDIA")
            urgency_context = f"\nNÍVEL DE URGÊNCIA DETECTADO: {urgency_label}\n- Use este nível de urgência ao mencionar urgência no resumo para manter consistência.\n- Se o nível detectado for {urgency_label}, mencione urgência {urgency_label.lower()} no resumo."
        
        prompt = f"""Você é um assistente especializado em análise de atendimentos imobiliários.

Analise o seguinte conteúdo de atendimento e gere um resumo profissional, conciso e útil em português brasileiro.

DATA ATUAL: {current_date}
{urgency_context}

REGRAS IMPORTANTES:
- NÃO copie o conteúdo original palavra por palavra
- Crie um resumo objetivo destacando os pontos principais
- Foque em: interesse do cliente, preferências (tipo de imóvel, localização, orçamento), urgência, sentimentos
- Use linguagem profissional mas acessível
- Seja específico sobre valores, localizações e preferências mencionadas
- Máximo de 200 palavras
- IMPORTANTE: Se um nível de urgência foi detectado acima, use EXATAMENTE esse nível ao mencionar urgência no resumo
- CRÍTICO: Se o conteúdo indicar que a VENDA/ALUGUEL FOI CONCLUÍDA (ex: "fechou a compra", "venda concretizada", "comprou o imóvel") ou que houve PERDA (cliente desistiu), destaque isso claramente no resumo. Nesses casos NÃO sugira agendar visita ou ações de prospecção - a negociação já foi finalizada

CONTEXTO TEMPORAL:
- Quando mencionar datas, compare com a data atual ({current_date})
- "Semana que vem", "próxima semana", "daqui alguns dias" são datas PRÓXIMAS, não distantes
- Considere "distante" apenas datas com mais de 1 mês de diferença
- Se uma visita foi agendada para a próxima semana, isso indica INTERESSE CONCRETO e URGÊNCIA MÉDIA/ALTA
- Não mencione que datas próximas (até 1 mês) estão "distantes"

CONTEÚDO DO ATENDIMENTO:
{processed_content}

RESUMO:"""
        
        try:
            result = gemini.chat(
                message=prompt,
                system_prompt="Você é um assistente especializado em análise de atendimentos imobiliários.",
            )
            
            if result.get("error"):
                logger.error(f"Error generating summary with Gemini: {result.get('error')}")
                # Fallback to simple extraction
                sentences = processed_content.split(".")
                important_sentences = [s.strip() for s in sentences if len(s.strip()) > 20][:3]
                summary = ". ".join(important_sentences)
                return summary if summary else processed_content[:200]
            
            summary = result.get("answer", "").strip()
            if summary:
                return summary
            
            # Fallback if empty response
            sentences = processed_content.split(".")
            important_sentences = [s.strip() for s in sentences if len(s.strip()) > 20][:3]
            summary = ". ".join(important_sentences)
            return summary if summary else processed_content[:200]
            
        except Exception as e:
            logger.error(f"Exception generating summary with Gemini: {e}", exc_info=True)
            # Fallback to simple extraction
            sentences = processed_content.split(".")
            important_sentences = [s.strip() for s in sentences if len(s.strip()) > 20][:3]
            summary = ". ".join(important_sentences)
            return summary if summary else processed_content[:200]

    @staticmethod
    def _extract_key_points(raw_content: str) -> dict[str, Any]:
        """Extract key points from raw content."""
        key_points = {
            "topics": [],
            "requirements": [],
            "mentions": [],
        }

        # Mock extraction
        if "quarto" in raw_content or "quartos" in raw_content:
            key_points["topics"].append("Número de quartos mencionado")
        if "orçamento" in raw_content or "preço" in raw_content or "valor" in raw_content:
            key_points["topics"].append("Orçamento/preço mencionado")
        if "zona" in raw_content or "bairro" in raw_content or "cidade" in raw_content:
            key_points["topics"].append("Localização mencionada")
        if "urgente" in raw_content or "rápido" in raw_content:
            key_points["mentions"].append("Urgência mencionada")

        return key_points

    @staticmethod
    def _detect_intent(raw_content: str) -> DetectedIntent | None:
        """Detect intent from raw content.
        IMPORTANT: Check sale/loss completion FIRST - these override all other intents.
        """
        content_lower = raw_content.lower()

        # Sale completed: venda/aluguel concretizado (overrides everything)
        sale_patterns = [
            "fechou a compra", "fechou a venda", "fechou o negócio", "fechou negócio",
            "fechando o negócio", "fechando a compra", "fechando a venda",
            "comprou o imóvel", "comprou o apartamento", "comprou a casa",
            "venda concretizada", "venda fechada", "negócio fechado",
            "alugou", "locação fechada", "locação concretizada",
            "concretizou a compra", "concretizou a venda", "concluiu a compra",
        ]
        if any(p in content_lower for p in sale_patterns):
            return DetectedIntent.SALE_COMPLETED

        # Loss: cliente desistiu / perda
        loss_patterns = [
            "desistiu", "perdeu o cliente", "cliente desistiu", "não quer mais",
            "desistiu da compra", "desistiu do negócio", "perda registrada",
        ]
        if any(p in content_lower for p in loss_patterns):
            return DetectedIntent.LOSS_REGISTERED

        if any(word in content_lower for word in ["visita", "agendar", "ver", "conhecer"]):
            return DetectedIntent.SCHEDULE_VISIT
        elif any(word in content_lower for word in ["preço", "valor", "negociar", "desconto"]):
            return DetectedIntent.PRICE_NEGOTIATION
        elif any(word in content_lower for word in ["buscar", "procurar", "encontrar", "disponível"]):
            return DetectedIntent.PROPERTY_SEARCH
        elif any(word in content_lower for word in ["documento", "papel", "contrato", "escritura"]):
            return DetectedIntent.DOCUMENTATION_REQUEST
        elif any(word in content_lower for word in ["reclamar", "problema", "erro", "insatisfeito"]):
            return DetectedIntent.COMPLAINT
        elif any(word in content_lower for word in ["retorno", "ligar", "contato", "falar"]):
            return DetectedIntent.GENERAL_INQUIRY
        else:
            return DetectedIntent.GENERAL_INQUIRY

    @staticmethod
    def _detect_interest_type(raw_content: str) -> InterestType | None:
        """Detect interest type from raw content."""
        content_lower = raw_content.lower()

        if any(word in content_lower for word in ["comprar", "compra", "adquirir"]):
            return InterestType.BUY
        elif any(word in content_lower for word in ["alugar", "aluguel", "locação"]):
            return InterestType.RENT
        elif any(word in content_lower for word in ["vender", "venda", "vender"]):
            return InterestType.SELL
        elif any(word in content_lower for word in ["investir", "investimento"]):
            return InterestType.INVEST

        return None

    @staticmethod
    def _detect_budget(raw_content: str) -> dict[str, float | None]:
        """Detect budget range from raw content."""
        import re

        # Normalize content: remove R$ and common words, normalize separators
        normalized = raw_content.replace("R$", "").replace("reais", "").replace("real", "")
        normalized = normalized.replace(",", ".")  # Convert comma to dot for decimal
        
        # Pattern 1: Numbers with thousands separator (500.000, 1.500.000)
        # Pattern 2: Numbers with "mil" (500 mil, 1.5 milhão)
        # Pattern 3: Plain numbers (500000)
        
        prices = []
        
        # Pattern 1: Numbers with dots (Brazilian format: 500.000)
        dot_pattern = r"(\d{1,3}(?:\.\d{3})*(?:\.\d+)?)"
        for match in re.finditer(dot_pattern, normalized):
            num_str = match.group(1).replace(".", "")
            try:
                num = float(num_str)
                if 50000 <= num <= 10000000:
                    prices.append(num)
            except ValueError:
                continue
        
        # Pattern 2: Numbers with "mil" or "milhão"
        mil_pattern = r"(\d+(?:[.,]\d+)?)\s*(?:mil|milh[oõ]es?|milh[oõ]es?)"
        for match in re.finditer(mil_pattern, normalized, re.IGNORECASE):
            num_str = match.group(1).replace(",", ".")
            try:
                num = float(num_str)
                # Convert to actual number
                if "milh" in match.group(0).lower():
                    num = num * 1000000
                else:
                    num = num * 1000
                if 50000 <= num <= 10000000:
                    prices.append(num)
            except ValueError:
                continue
        
        # Pattern 3: Plain numbers (fallback)
        if not prices:
            numbers = re.findall(r"\d+(?:[.,]\d+)?", normalized)
            for num_str in numbers:
                try:
                    # Try as-is first
                    num = float(num_str.replace(",", "."))
                    # If it's a reasonable price range, use it
                    if 50000 <= num <= 10000000:
                        prices.append(num)
                    # If it's a small number but in context of "mil", multiply
                    elif 1 <= num <= 10000 and "mil" in normalized.lower():
                        num = num * 1000
                        if 50000 <= num <= 10000000:
                            prices.append(num)
                except ValueError:
                    continue

        if prices:
            min_price = min(prices)
            max_price = max(prices)
            # If only one price, assume it's max and min is 70% of it
            if len(prices) == 1:
                return {"min": min_price * 0.7, "max": min_price}
            return {"min": min_price, "max": max_price}

        return {"min": None, "max": None}

    @staticmethod
    def _detect_urgency(raw_content: str) -> UrgencyLevel | None:
        """
        Detect urgency level from raw content.
        
        Priority order:
        0. SALE/LOSS - if sale completed or loss registered, urgency is LOW (no action needed)
        1. IMMEDIATE - explicit urgent/immediate keywords
        2. HIGH - short-term timelines (days, next week)
        3. MEDIUM - medium-term timelines (weeks, months up to 6)
        4. LOW - long-term or no timeline
        """
        import re
        content_lower = raw_content.lower()

        # Sale or loss completed → no urgency (LOW)
        sale_loss_patterns = [
            "fechou a compra", "fechou a venda", "fechou o negócio", "fechou negócio",
            "fechando o negócio", "fechando a compra", "comprou o imóvel",
            "venda concretizada", "venda fechada", "negócio fechado",
            "alugou", "locação fechada", "concretizou a compra", "concluiu a compra",
            "desistiu", "perdeu o cliente", "cliente desistiu", "perda registrada",
        ]
        if any(p in content_lower for p in sale_loss_patterns):
            return UrgencyLevel.LOW

        # Immediate urgency indicators
        if any(word in content_lower for word in ["imediato", "urgente", "hoje", "agora", "rápido", "já", "imediatamente", "asap"]):
            return UrgencyLevel.IMMEDIATE
        
        # High urgency: next week, few days, soon (avoid "próximo" alone - it matches "próximo mês" → medium)
        high_urgency_patterns = [
            "semana que vem", "próxima semana", "logo", "breve", "em breve",
            "daqui alguns dias", "daqui poucos dias", "nos próximos dias", "essa semana",
            "em dias", "em algumas semanas", "nas próximas semanas"
        ]
        if any(pattern in content_lower for pattern in high_urgency_patterns):
            return UrgencyLevel.HIGH
        
        # Check for numeric timeframes (e.g., "em 3 dias", "em 2 semanas")
        # High: 1-14 days, 1-2 weeks
        numeric_high = re.search(r"em\s+(\d+)\s+(dia|dias|semana|semanas)", content_lower)
        if numeric_high:
            number = int(numeric_high.group(1))
            unit = numeric_high.group(2)
            if (unit in ["dia", "dias"] and number <= 14) or (unit in ["semana", "semanas"] and number <= 2):
                return UrgencyLevel.HIGH
        
        # Medium urgency: thinking, evaluating, medium-term timelines (1-6 months)
        medium_urgency_patterns = [
            "pensando", "avaliando", "considerando", "mês que vem", "próximo mês",
            "em questão de", "em alguns meses", "nos próximos meses"
        ]
        if any(pattern in content_lower for pattern in medium_urgency_patterns):
            return UrgencyLevel.MEDIUM
        
        # Check for numeric timeframes for medium (3-6 months)
        numeric_medium = re.search(r"em\s+(\d+)\s+(mês|meses|semana|semanas)", content_lower)
        if numeric_medium:
            number = int(numeric_medium.group(1))
            unit = numeric_medium.group(2)
            if (unit in ["mês", "meses"] and 1 <= number <= 6) or (unit in ["semana", "semanas"] and 3 <= number <= 8):
                return UrgencyLevel.MEDIUM
        
        # Also check for "em X meses" patterns
        months_pattern = re.search(r"(\d+)\s*(?:a|até|ou)\s*(\d+)?\s*m(?:ês|es)", content_lower)
        if months_pattern:
            num1 = int(months_pattern.group(1))
            num2 = int(months_pattern.group(2)) if months_pattern.group(2) else num1
            if num1 <= 6 or num2 <= 6:
                return UrgencyLevel.MEDIUM
        
        # Low urgency: no clear timeline or distant future
        if any(word in content_lower for word in ["futuro", "depois", "mais tarde", "sem pressa", "sem urgência", "longo prazo"]):
            return UrgencyLevel.LOW
        
        # Check for long-term numeric timeframes (> 6 months)
        numeric_low = re.search(r"em\s+(\d+)\s+(mês|meses)", content_lower)
        if numeric_low:
            number = int(numeric_low.group(1))
            if number > 6:
                return UrgencyLevel.LOW
        
        # Default to medium if there's any indication of interest (conservative approach)
        if any(word in content_lower for word in ["interesse", "gostaria", "quero", "preciso", "buscar", "procurar", "deseja"]):
            return UrgencyLevel.MEDIUM
        
        return UrgencyLevel.LOW

    @staticmethod
    def _suggest_lead_score(
        interest_type: InterestType | None,
        urgency_level: UrgencyLevel | None,
        budget_range: dict[str, float | None],
        detected_intent: DetectedIntent | None,
    ) -> int:
        """Suggest lead score based on detected information."""
        score = 30  # Base score

        # Interest type detected (+20)
        if interest_type:
            score += 20

        # Urgency level
        if urgency_level == UrgencyLevel.IMMEDIATE:
            score += 25
        elif urgency_level == UrgencyLevel.HIGH:
            score += 15
        elif urgency_level == UrgencyLevel.MEDIUM:
            score += 10
        elif urgency_level == UrgencyLevel.LOW:
            score += 5

        # Budget detected (+15)
        if budget_range.get("min") or budget_range.get("max"):
            score += 15

        # Intent
        if detected_intent == DetectedIntent.SALE_COMPLETED:
            return 100  # Conversion = max score
        elif detected_intent == DetectedIntent.LOSS_REGISTERED:
            return min(score, 25)  # Loss = low score
        elif detected_intent == DetectedIntent.SCHEDULE_VISIT:
            score += 10
        elif detected_intent == DetectedIntent.PRICE_NEGOTIATION:
            score += 8

        return min(score, 100)  # Cap at 100

    @staticmethod
    def _detect_sentiment(raw_content: str) -> Sentiment:
        """Detect sentiment from raw content using AI when available."""
        gemini = AISummaryService._get_gemini_service()
        
        # If Gemini is configured, use AI for better sentiment analysis
        if gemini.is_configured():
            try:
                prompt = f"""Analise o sentimento do seguinte atendimento imobiliário e retorne APENAS uma das opções: POSITIVE, NEGATIVE, NEUTRAL, ou MIXED.

Considere:
- POSITIVE: Cliente demonstra interesse, entusiasmo, satisfação, vontade de avançar
- NEGATIVE: Cliente demonstra desinteresse, insatisfação, reclamações, frustração
- NEUTRAL: Cliente está apenas informando, sem emoção clara, ou tom profissional neutro
- MIXED: Cliente tem sentimentos contraditórios (gostou de algo mas não de outro)

ATENDIMENTO:
{raw_content}

Responda APENAS com uma palavra: POSITIVE, NEGATIVE, NEUTRAL ou MIXED"""
                
                result = gemini.chat(
                    message=prompt,
                    system_prompt="Você é um especialista em análise de sentimento em atendimentos imobiliários. Retorne apenas uma palavra: POSITIVE, NEGATIVE, NEUTRAL ou MIXED.",
                )
                
                answer = result.get("answer", "").strip().upper()
                
                # Map AI response to Sentiment enum
                if "POSITIVE" in answer:
                    return Sentiment.POSITIVE
                elif "NEGATIVE" in answer:
                    return Sentiment.NEGATIVE
                elif "MIXED" in answer:
                    return Sentiment.MIXED
                else:
                    # Fallback to neutral if unclear
                    return Sentiment.NEUTRAL
                    
            except Exception as e:
                logger.warning(f"Error detecting sentiment with AI, using fallback: {e}")
                # Fall through to fallback method
        
        # Fallback: Simple keyword-based detection
        content_lower = raw_content.lower()

        positive_words = [
            "interessado", "gostei", "ótimo", "perfeito", "excelente", "adoro", 
            "gostaria", "quero", "preciso", "interesse", "legal", "bom", "bom demais",
            "maravilhoso", "incrível", "fantástico", "top", "show", "amei"
        ]
        negative_words = [
            "não gostei", "ruim", "caro", "problema", "insatisfeito", "desapontado",
            "não quero", "não preciso", "não gosto", "péssimo", "horrível", "não serve",
            "muito caro", "caro demais", "não me interessa"
        ]

        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)

        if positive_count > negative_count:
            return Sentiment.POSITIVE
        elif negative_count > positive_count:
            return Sentiment.NEGATIVE
        elif positive_count > 0 and negative_count > 0:
            return Sentiment.MIXED
        else:
            return Sentiment.NEUTRAL

    @staticmethod
    def _calculate_confidence(
        raw_content: str,
        interest_type: InterestType | None,
        budget_range: dict[str, float | None],
    ) -> float:
        """Calculate confidence score (0.0-1.0) based on data quality."""
        confidence = 0.3  # Base confidence

        # More content = higher confidence
        if len(raw_content) > 100:
            confidence += 0.2
        elif len(raw_content) > 50:
            confidence += 0.1

        # Interest type detected
        if interest_type:
            confidence += 0.2

        # Budget detected
        if budget_range.get("min") or budget_range.get("max"):
            confidence += 0.2

        # Specific keywords
        specific_keywords = ["quarto", "banheiro", "garagem", "área", "bairro", "cidade"]
        found_keywords = sum(1 for keyword in specific_keywords if keyword in raw_content.lower())
        confidence += min(found_keywords * 0.05, 0.1)

        return min(confidence, 1.0)
    
    @staticmethod
    def _extract_city(raw_content: str) -> str | None:
        """Extract city name from raw content using AI when available, fallback to regex."""
        import re
        
        # Try using AI first if available (more accurate)
        gemini = AISummaryService._get_gemini_service()
        if gemini.is_configured():
            try:
                prompt = f"""Analise o seguinte texto de atendimento imobiliário e extraia APENAS o nome da cidade mencionada.

IMPORTANTE:
- Extraia APENAS o nome da cidade (ex: "Ourinhos", "São Paulo", "Rio de Janeiro")
- NÃO extraia frases como "concretizar a compra", "visualizada através", etc.
- Se mencionar "casa em Ourinhos", extraia "Ourinhos"
- Se mencionar "cidade de X", extraia "X"
- Se não houver cidade mencionada, retorne null
- Retorne APENAS o nome da cidade ou "null" se não houver

TEXTO:
{raw_content[:2000]}

Responda APENAS com o nome da cidade ou "null":"""
                
                result = gemini.chat(
                    message=prompt,
                    system_prompt="Você é um especialista em extrair nomes de cidades de textos. Retorne APENAS o nome da cidade ou 'null'.",
                )
                
                answer = result.get("answer", "").strip()
                
                # Clean up the answer
                answer = answer.replace('"', '').replace("'", "").strip()
                
                # Check if it's null or empty
                if answer.lower() in ['null', 'none', 'não', 'nao', ''] or len(answer) < 3:
                    # Fall through to regex
                    pass
                else:
                    # Validate it's not a verb phrase
                    action_verbs = {'concretizar', 'visualizar', 'indicar', 'demonstrar', 'solicitar', 
                                   'agendar', 'reforçar', 'possuir', 'desejar', 'querer', 'precisar',
                                   'concretização', 'visualização', 'demonstração', 'solicitação'}
                    words = answer.split()
                    if words and words[0].lower() not in action_verbs:
                        # Additional check: should not be a long phrase
                        if len(words) <= 3 and len(answer) <= 50:
                            return answer.title() if answer.islower() else answer
            except Exception as e:
                logger.warning(f"Error extracting city with AI, using regex fallback: {e}")
                # Fall through to regex
        
        # Fallback to regex-based extraction
        content_lower = raw_content.lower()
        
        # Common skip words that are not cities (expanded list)
        skip_words = {
            "casa", "apartamento", "imóvel", "terreno", "comprar", "compra", "alugar", "vender",
            "buscar", "procurar", "quer", "uma", "um", "breve", "geral", "qualquer",
            "lugar", "algum", "alguma", "deseja", "desejo", "preciso", "precisa",
            "orçamento", "orçamento", "valor", "preço", "mil", "milhão", "reais",
            "concretizar", "concretização", "concretiza", "concretizado", "concretizando",
            "visualizada", "visualizado", "visualizar", "visualização", "visualizando",
            "através", "indicando", "indicado", "indicou", "indica",
            "demonstrou", "demonstrar", "demonstração", "demonstrado",
            "grande", "interesse", "possui", "possuiu", "possuir",
            "solicitação", "solicitar", "solicitado", "solicitou",
            "agendar", "agendamento", "agendado", "agendou",
            "visita", "visitar", "visitado", "visitou",
            "reforça", "reforçar", "reforçado", "reforçou",
            "apenas", "após", "atual", "data", "dias", "dia",
            "horas", "hora", "às", "as", "no", "na", "em", "para",
            "visualizado", "visualizada", "visualizar", "visualização",
            "instagram", "facebook", "site", "internet", "web"
        }
        
        # Try uppercase patterns first (more reliable for city names)
        # Priority order: most specific patterns first
        uppercase_patterns = [
            # "casa em Ourinhos", "apartamento em Ourinhos" - HIGHEST PRIORITY (most specific)
            r"(?:casa|apartamento|terreno|imóvel)\s+(?:em|de|na|no)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:do|da|de|dos|das)?\s*[A-ZÀ-Ú][a-zà-ú]+)*)",
            # "na cidade de Ourinhos" - HIGH PRIORITY
            r"na\s+cidade\s+(?:de|do|da)?\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:do|da|de|dos|das)?\s*[A-ZÀ-Ú][a-zà-ú]+)*)",
            # "cidade de Ourinhos" - HIGH PRIORITY
            r"cidade\s+(?:de|do|da)?\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:do|da|de|dos|das)?\s*[A-ZÀ-Ú][a-zà-ú]+)*)",
            # "morar em Ourinhos" - MEDIUM PRIORITY
            r"morar\s+em\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Úa-zà-ú]+)*)",
            # "imóvel em Ourinhos" - MEDIUM PRIORITY
            r"imóvel\s+em\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Úa-zà-ú]+)*)",
            # "em Ourinhos", "em São Paulo" - LOW PRIORITY (less specific, more prone to errors)
            # Only match if it's at word boundary and not after a verb
            r"(?:^|\.|,|;|:|\s)(?:em|na|no|para)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:do|da|de|dos|das)?\s*[A-ZÀ-Ú][a-zà-ú]+)*)",
        ]
        
        for pattern in uppercase_patterns:
            matches = re.findall(pattern, raw_content)
            if matches:
                for match in matches:
                    city = match.strip()
                    # Skip if it's a common word or too short
                    if city.lower() not in skip_words and len(city) > 2:
                        # City names are usually 1-4 words
                        words = city.split()
                        if len(words) <= 4:
                            # Check if any word is in skip list
                            if not any(word.lower() in skip_words for word in words):
                                # Additional validation: city should not be a verb phrase
                                # Skip if it looks like "Concretizar A Compra" (verb + article + noun)
                                if not re.match(r'^[A-ZÀ-Ú][a-zà-ú]+\s+(?:a|o|as|os|de|do|da|dos|das)\s+[A-ZÀ-Ú][a-zà-ú]+$', city):
                                    # Skip if it contains common action verbs
                                    action_verbs = {'concretizar', 'visualizar', 'indicar', 'demonstrar', 'solicitar', 
                                                   'agendar', 'reforçar', 'possuir', 'desejar', 'querer', 'precisar'}
                                    first_word_lower = words[0].lower()
                                    if first_word_lower not in action_verbs:
                                        return city
        
        # Also check for cities mentioned with lowercase after prepositions
        # This catches cases like "em ourinhos" (lowercase)
        lowercase_patterns = [
            # "na cidade de ourinhos" - specific pattern for lowercase (highest priority)
            r"na\s+cidade\s+(?:de|do|da)?\s+([a-zà-ú]+(?:\s+(?:do|da|de|dos|das)?\s*[a-zà-ú]+)*)",
            # "casa em ourinhos", "apartamento em ourinhos" - specific pattern for property + city
            r"(?:casa|apartamento|terreno|imóvel)\s+(?:em|de|na|no)\s+([a-zà-ú]+(?:\s+(?:do|da|de|dos|das)?\s*[a-zà-ú]+)*)",
            r"cidade\s+(?:de|do|da)?\s+([a-zà-ú]+(?:\s+[a-zà-ú]+)*)",
            r"(?:^|\.|,|;|:|\s)(?:em|na|no|para)\s+([a-zà-ú]+(?:\s+(?:do|da|de|dos|das)?\s*[a-zà-ú]+)*)",
        ]
        
        for pattern in lowercase_patterns:
            matches = re.findall(pattern, content_lower)
            if matches:
                for match in matches:
                    city = match.strip()
                    # Skip if it's a common word, too short, or contains numbers
                    if (city.lower() not in skip_words and 
                        len(city) > 3 and 
                        not re.search(r'\d', city) and
                        len(city.split()) <= 3):
                        # Check if any word is in skip list
                        words = city.split()
                        if not any(word.lower() in skip_words for word in words):
                            # Additional validation: skip verb phrases
                            action_verbs = {'concretizar', 'visualizar', 'indicar', 'demonstrar', 'solicitar', 
                                           'agendar', 'reforçar', 'possuir', 'desejar', 'querer', 'precisar'}
                            first_word_lower = words[0].lower()
                            if first_word_lower not in action_verbs:
                                # Capitalize properly
                                return city.title()
        
        return None
    
    @staticmethod
    def _extract_property_type(raw_content: str) -> PropertyTypeEnum | None:
        """Extract property type from raw content."""
        content_lower = raw_content.lower()
        
        # Map keywords to property types
        type_keywords = {
            PropertyTypeEnum.HOUSE: ["casa", "residencial", "sobrado", "casa térrea"],
            PropertyTypeEnum.APARTMENT: ["apartamento", "apto", "ap", "flat"],
            PropertyTypeEnum.LAND: ["terreno", "lote", "chácara", "sítio"],
            PropertyTypeEnum.COMMERCIAL: ["comercial", "loja", "sala comercial", "galpão", "escritório"],
            PropertyTypeEnum.RURAL: ["rural", "fazenda", "sítio", "chácara"],
        }
        
        for prop_type, keywords in type_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                return prop_type
        
        return None
    
    @staticmethod
    def _recommend_properties(
        db: Session,
        client_id: uuid.UUID,
        interest_type: str | None = None,
        property_type: str | None = None,
        city: str | None = None,
        budget_min: float | None = None,
        budget_max: float | None = None,
    ) -> list[uuid.UUID] | None:
        """
        Recommend properties based on client preferences extracted from attendance.
        
        Args:
            db: Database session
            client_id: Client UUID
            interest_type: Detected interest type (BUY, RENT, etc.)
            property_type: Detected property type string (HOUSE, APARTMENT, etc.)
            city: Detected city of interest
            budget_min: Minimum budget detected
            budget_max: Maximum budget detected
        
        Returns:
            List of recommended property UUIDs (max 5) or None if no matches
        """
        try:
            property_repo = PropertyRepository(db)
            
            # Convert property_type string to PropertyTypeEnum if provided
            # Note: PropertyRepository expects PropertyType from app.properties.models
            from app.properties.models import PropertyType as PropType
            property_type_enum = None
            if property_type:
                try:
                    property_type_enum = PropType(property_type)
                except ValueError:
                    logger.warning(f"Invalid property type: {property_type}, ignoring")
                    property_type_enum = None
            
            # Find recommended properties
            properties = property_repo.find_recommended_properties(
                interest_type=interest_type,
                property_type=property_type_enum,
                city=city,
                budget_min=budget_min,
                budget_max=budget_max,
                limit=5,  # Return top 5 recommendations
            )
            
            if not properties:
                logger.info(f"No properties found matching criteria for client {client_id}")
                return None
            
            # Return list of property IDs as strings (for JSON serialization)
            property_ids = [str(prop.id) for prop in properties]
            logger.info(f"Found {len(property_ids)} recommended properties for client {client_id}")
            return property_ids
            
        except Exception as e:
            logger.error(f"Error recommending properties: {e}", exc_info=True)
            return None

    @staticmethod
    def detect_visit_intent(
        raw_content: str,
        client_id: uuid.UUID | None = None,
        property_id: uuid.UUID | None = None,
        agent_id: uuid.UUID | None = None,
    ) -> dict[str, Any] | None:
        """
        Detect visit intent from raw content using AI.
        
        Analyzes the conversation to identify if the client wants to schedule a visit,
        extracts date, time, and validates the information.
        
        Args:
            raw_content: Raw content of the attendance/conversation
            client_id: Optional client ID for context
            property_id: Optional property ID if visit is for a specific property
            agent_id: Optional agent ID (will be used as broker_id for visit)
            
        Returns:
            Dictionary with visit information if detected, None otherwise:
            {
                "detected": True,
                "scheduled_at": "2024-02-15T14:30:00",  # ISO format datetime
                "date": "15/02/2024",  # Human-readable date
                "time": "14:30",  # Human-readable time
                "confidence": 0.85,  # Confidence score (0-1)
                "extracted_text": "Cliente quer visitar no dia 15/02 às 14:30",
                "property_id": uuid.UUID | None,  # Property mentioned or provided
                "notes": "Visita agendada durante atendimento"
            }
            Or None if no visit intent detected
        """
        try:
            gemini = AISummaryService._get_gemini_service()
            
            # Truncate content if too large
            processed_content = AISummaryService._truncate_content_intelligently(raw_content, max_chars=50000)
            
            # If Gemini is not configured, use regex-based fallback
            if not gemini.is_configured():
                logger.warning("Gemini API not configured, using regex-based visit detection")
                return AISummaryService._detect_visit_intent_regex(processed_content, property_id)
            
            # Use Gemini to detect visit intent
            from datetime import datetime, timedelta, timezone
            
            # Get current date/time in Brazil timezone (UTC-3)
            # When user says "14h", they mean 14h Brazil time, not UTC
            brazil_tz = timezone(timedelta(hours=-3))  # UTC-3 (Brasil)
            current_date_utc = datetime.now(timezone.utc)
            current_date_brazil = current_date_utc.astimezone(brazil_tz)
            current_date_str = current_date_brazil.strftime("%d/%m/%Y")
            current_time_str = current_date_brazil.strftime("%H:%M")
            current_year = current_date_brazil.year
            
            # Build context
            context = ""
            if property_id:
                context += f"\nPROPRIEDADE MENCIONADA: ID {property_id}\n"
            if client_id:
                context += f"\nCLIENTE: ID {client_id}\n"
            
            prompt = f"""Você é um assistente especializado em detectar intenções de agendamento de visitas imobiliárias.

Analise o seguinte conteúdo de conversa e identifique se o cliente expressou desejo de agendar uma visita a um imóvel.

DATA ATUAL: {current_date_str} ({current_year})
HORA ATUAL: {current_time_str} (horário do Brasil, UTC-3)
ANO ATUAL: {current_year}
FUSO HORÁRIO: Brasil (UTC-3)
{context}

CONTEÚDO DA CONVERSA:
{processed_content}

INSTRUÇÕES:
1. Identifique se há MENÇÃO EXPLÍCITA de agendamento de visita (ex: "quero visitar", "podemos marcar", "agendar visita", "quero ver o imóvel", "visitar na data X", etc.)
2. Se detectar intenção de visita, extraia:
   - DATA: no formato DD/MM/YYYY (se mencionada)
   - HORA: no formato HH:MM (se mencionada) - IMPORTANTE: horário mencionado é horário do Brasil (UTC-3)
   - Se apenas dia da semana for mencionado (ex: "segunda-feira"), calcule a data considerando a data atual
   - Se apenas data parcial for mencionada (ex: "dia 15"), assuma o mês atual ou próximo se já passou
   - Se ano não for mencionado, assuma o ano atual ({current_year}) ou próximo se a data já passou
3. VALIDAÇÕES:
   - Data não pode ser no passado (se mencionada data passada, retorne null)
   - Data deve ser válida (ex: não pode ser 31/02)
   - Hora deve estar entre 08:00 e 20:00 (horário comercial do Brasil)
   - Se apenas horário for mencionado sem data, assuma "hoje" se ainda não passou, senão "amanhã"
4. Se NÃO houver intenção clara de agendamento, retorne null
5. Se a data mencionada for ambígua ou inválida, retorne null

Responda APENAS com um JSON válido no formato:
{{
    "detected": true,
    "scheduled_at": "2024-02-15T14:30:00-03:00",  // ISO format datetime (horário do Brasil, UTC-3)
    "date": "15/02/2024",  // Human-readable date (DD/MM/YYYY)
    "time": "14:30",  // Human-readable time (HH:MM) - horário do Brasil
    "confidence": 0.85,  // Confidence score 0-1
    "extracted_text": "Cliente quer visitar no dia 15/02 às 14:30",
    "notes": "Visita agendada durante atendimento"
}}

OU, se não detectar intenção de visita:
{{
    "detected": false
}}

IMPORTANTE:
- Se detectar intenção, o campo "scheduled_at" DEVE estar no formato ISO 8601 com timezone UTC-3 (YYYY-MM-DDTHH:MM:SS-03:00)
- O horário mencionado pelo cliente é SEMPRE horário do Brasil (UTC-3)
- Se o cliente diz "14h", isso significa 14:00 no horário do Brasil, não UTC
- Se a data/hora mencionada for relativa (ex: "amanhã às 14h"), calcule a data absoluta baseada na data atual do Brasil
- Se apenas parte da informação estiver presente (ex: só data sem hora), use valores padrão razoáveis (ex: 14:00 para hora)"""

            try:
                result = gemini.chat(
                    message=prompt,
                    system_prompt="Você é um assistente especializado em detectar intenções de agendamento de visitas imobiliárias. Responda APENAS com JSON válido.",
                )
                
                if result.get("error"):
                    logger.error(f"Error detecting visit intent with Gemini: {result.get('error')}")
                    return AISummaryService._detect_visit_intent_regex(processed_content, property_id)
                
                answer = result.get("answer", "").strip()
                if not answer:
                    return None
                
                # Try to extract JSON from the answer (might have markdown code blocks)
                import json
                import re
                
                # Remove markdown code blocks if present
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', answer, re.DOTALL)
                if json_match:
                    answer = json_match.group(1)
                else:
                    # Try to find JSON object in the answer
                    json_match = re.search(r'\{.*\}', answer, re.DOTALL)
                    if json_match:
                        answer = json_match.group(0)
                
                parsed = json.loads(answer)
                
                if not parsed.get("detected", False):
                    return None
                
                # Validate and convert scheduled_at to datetime
                scheduled_at_str = parsed.get("scheduled_at")
                if not scheduled_at_str:
                    return None
                
                try:
                    # Parse ISO format datetime
                    # IMPORTANTE: Horário mencionado pelo usuário é horário do Brasil (UTC-3)
                    # A IA deve retornar com timezone -03:00, mas se não tiver, assumimos horário do Brasil
                    brazil_tz = timezone(timedelta(hours=-3))  # UTC-3 (Brasil)
                    
                    if scheduled_at_str.endswith('Z'):
                        # Se termina com Z, assume UTC mas deveria ser Brasil - converter
                        scheduled_at = datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
                        # Converter de UTC para horário do Brasil (assumindo que foi erro da IA)
                        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc).astimezone(brazil_tz)
                    elif '-03:00' in scheduled_at_str or '+03:00' in scheduled_at_str:
                        # Já tem timezone do Brasil
                        scheduled_at = datetime.fromisoformat(scheduled_at_str)
                    elif '+' in scheduled_at_str or (scheduled_at_str.count('-') > 2 and not scheduled_at_str.endswith('-03:00')):
                        # Tem outro timezone, converter para Brasil
                        scheduled_at = datetime.fromisoformat(scheduled_at_str)
                        scheduled_at = scheduled_at.astimezone(brazil_tz)
                    else:
                        # Sem timezone - assumir que é horário do Brasil (UTC-3)
                        scheduled_at = datetime.fromisoformat(scheduled_at_str)
                        scheduled_at = scheduled_at.replace(tzinfo=brazil_tz)
                    
                    # Garantir que está no timezone do Brasil
                    if scheduled_at.tzinfo is None:
                        scheduled_at = scheduled_at.replace(tzinfo=brazil_tz)
                    elif scheduled_at.tzinfo != brazil_tz:
                        scheduled_at = scheduled_at.astimezone(brazil_tz)
                    
                    # Converter para UTC para armazenar no banco (padrão)
                    scheduled_at_utc = scheduled_at.astimezone(timezone.utc)
                    
                    # Validate: date cannot be in the past (comparar no timezone do Brasil)
                    if scheduled_at < current_date_brazil:
                        logger.warning(f"Detected visit date is in the past: {scheduled_at_str}, ignoring")
                        return None
                    
                    # Validate: hour should be between 08:00 and 20:00 (horário do Brasil)
                    hour_brazil = scheduled_at.hour
                    if hour_brazil < 8 or hour_brazil >= 20:
                        logger.warning(f"Detected visit hour is outside business hours: {hour_brazil}, adjusting to 14:00")
                        scheduled_at = scheduled_at.replace(hour=14, minute=0)
                        scheduled_at_utc = scheduled_at.astimezone(timezone.utc)
                    
                    # Build response - retornar horário em UTC para o frontend converter se necessário
                    # Mas também retornar date/time formatados no horário do Brasil para exibição
                    visit_info = {
                        "detected": True,
                        "scheduled_at": scheduled_at_utc.isoformat(),  # UTC para armazenar no banco
                        "date": parsed.get("date", scheduled_at.strftime("%d/%m/%Y")),  # Data no horário do Brasil
                        "time": parsed.get("time", scheduled_at.strftime("%H:%M")),  # Hora no horário do Brasil
                        "confidence": min(max(parsed.get("confidence", 0.7), 0.0), 1.0),  # Clamp between 0 and 1
                        "extracted_text": parsed.get("extracted_text", ""),
                        "property_id": str(property_id) if property_id else None,
                        "notes": parsed.get("notes", "Visita agendada durante atendimento"),
                    }
                    
                    logger.info(f"Visit intent detected: {visit_info}")
                    return visit_info
                    
                except (ValueError, TypeError) as e:
                    logger.error(f"Error parsing scheduled_at: {scheduled_at_str}, error: {e}")
                    return None
                    
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON from Gemini response: {e}, answer: {answer}")
                return AISummaryService._detect_visit_intent_regex(processed_content, property_id)
            except Exception as e:
                logger.error(f"Exception detecting visit intent with Gemini: {e}", exc_info=True)
                return AISummaryService._detect_visit_intent_regex(processed_content, property_id)
                
        except Exception as e:
            logger.error(f"Error in detect_visit_intent: {e}", exc_info=True)
            return None

    @staticmethod
    def detect_loss_intent(
        raw_content: str,
        client_id: uuid.UUID | None = None,
        property_id: uuid.UUID | None = None,
        agent_id: uuid.UUID | None = None,
        attendance_status: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Detect loss intent from raw content using AI.
        
        ⚠️ IMPORTANT: This is ONLY a suggestion. It does NOT change attendance status.
        The attendance remains ACTIVE until the user explicitly confirms the loss.
        
        Analyzes the conversation to identify if the client has given up or lost interest,
        extracts loss reason, stage, and detailed information.
        
        Args:
            raw_content: Raw content of the attendance/conversation
            client_id: Optional client ID for context
            property_id: Optional property ID if loss is for a specific property
            agent_id: Optional agent ID
            attendance_status: Current attendance status (if LOST, detection is skipped)
            
        Returns:
            Dictionary with loss information if detected, None otherwise:
            {
                "detected": True,
                "loss_reason": "CLIENT_FINANCING_DENIED",  # LossReason enum value
                "loss_stage": "NEGOTIATION",  # LossStage enum value
                "confidence": 0.85,  # Confidence score (0-1)
                "extracted_text": "Cliente não conseguiu o consórcio e não quer mais o imóvel",
                "detailed_reason": "Cliente não conseguiu aprovação do consórcio",
                "client_feedback": "Não conseguiu o consórcio e infelizmente não quer mais o imóvel"
            }
            Or None if no loss intent detected
        """
        # ⚠️ PROTECTION 1: Don't detect loss if attendance is already LOST
        # This prevents multiple detections and annoying popups
        if attendance_status == "LOST":
            logger.info("Skipping loss detection: attendance is already LOST")
            return None
        
        try:
            gemini = AISummaryService._get_gemini_service()
            
            # Truncate content if too large
            processed_content = AISummaryService._truncate_content_intelligently(raw_content, max_chars=50000)
            
            # If Gemini is not configured, use regex-based fallback
            if not gemini.is_configured():
                logger.warning("Gemini API not configured, using regex-based loss detection")
                return AISummaryService._detect_loss_intent_regex(processed_content)
            
            # Build context
            context = ""
            if property_id:
                context += f"\nPROPRIEDADE: ID {property_id}\n"
            if client_id:
                context += f"\nCLIENTE: ID {client_id}\n"
            
            prompt = f"""Você é um assistente especializado em detectar quando um cliente desistiu ou perdeu interesse em um imóvel.

Analise o seguinte conteúdo de conversa e identifique se o cliente expressou desistência, perda de interesse, ou motivo para não continuar com a negociação.

{context}

CONTEÚDO DA CONVERSA:
{processed_content}

INSTRUÇÕES:
1. Identifique se há MENÇÃO EXPLÍCITA de desistência, perda de interesse, ou motivo para não continuar:
   - "não quer mais", "desistiu", "não conseguiu", "não vai mais", "cancelou"
   - Problemas com financiamento/consórcio
   - Mudança de ideia
   - Problemas com o imóvel
   - Preço muito alto
   - Orçamento insuficiente
   - Escolheu outro imóvel/concorrência
2. Se detectar perda, identifique:
   - MOTIVO PRINCIPAL (use um dos valores do enum LossReason):
     * CLIENT_FINANCING_DENIED: Financiamento/consórcio negado ou não aprovado
     * CLIENT_CHANGED_MIND: Cliente mudou de ideia
     * PRICE_TOO_HIGH: Preço muito alto
     * BUDGET_INSUFFICIENT: Orçamento insuficiente
     * BETTER_OFFER_COMPETITOR: Escolheu outro imóvel/concorrência
     * PROPERTY_NOT_SUITABLE: Imóvel não adequado
     * LOCATION_NOT_IDEAL: Localização não ideal
     * CLIENT_NOT_READY: Cliente não está pronto
     * ECONOMIC_FACTORS: Fatores econômicos
     * PERSONAL_REASONS: Motivos pessoais
     * OTHER: Outro motivo
   - ESTÁGIO (use um dos valores do enum LossStage):
     * INITIAL_CONTACT: Contato inicial
     * QUALIFICATION: Qualificação
     * VISIT_SCHEDULED: Visita agendada
     * VISIT_COMPLETED: Visita realizada
     * PROPOSAL: Proposta
     * NEGOTIATION: Negociação
     * CONTRACT: Contrato
   - EXPLICAÇÃO DETALHADA: Extraia o motivo detalhado mencionado
   - FEEDBACK DO CLIENTE: Extraia o feedback direto do cliente
3. Se NÃO houver indicação clara de perda, retorne null

Responda APENAS com um JSON válido no formato:
{{
    "detected": true,
    "loss_reason": "CLIENT_FINANCING_DENIED",
    "loss_stage": "NEGOTIATION",
    "confidence": 0.85,
    "extracted_text": "Cliente não conseguiu o consórcio e não quer mais o imóvel",
    "detailed_reason": "Cliente não conseguiu aprovação do consórcio",
    "client_feedback": "Não conseguiu o consórcio e infelizmente não quer mais o imóvel"
}}

OU, se não detectar perda:
{{
    "detected": false
}}

IMPORTANTE:
- Seja conservador: só detecte perda se houver indicação CLARA de desistência
- Use os valores exatos dos enums LossReason e LossStage
- Extraia o máximo de informação possível do texto"""

            try:
                result = gemini.chat(
                    message=prompt,
                    system_prompt="Você é um assistente especializado em detectar quando clientes desistem de negociações imobiliárias. Responda APENAS com JSON válido.",
                )
                
                if result.get("error"):
                    logger.error(f"Error detecting loss intent with Gemini: {result.get('error')}")
                    return AISummaryService._detect_loss_intent_regex(processed_content, attendance_status)
                
                answer = result.get("answer", "").strip()
                if not answer:
                    return None
                
                # Try to extract JSON from the answer
                import json
                import re
                
                # Remove markdown code blocks if present
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', answer, re.DOTALL)
                if json_match:
                    answer = json_match.group(1)
                else:
                    # Try to find JSON object in the answer
                    json_match = re.search(r'\{.*\}', answer, re.DOTALL)
                    if json_match:
                        answer = json_match.group(0)
                
                parsed = json.loads(answer)
                
                if not parsed.get("detected", False):
                    return None
                
                # Validate loss_reason and loss_stage
                from app.losses.models import LossReason, LossStage
                
                loss_reason = parsed.get("loss_reason")
                if loss_reason:
                    try:
                        LossReason(loss_reason)  # Validate enum value
                    except ValueError:
                        logger.warning(f"Invalid loss_reason: {loss_reason}, using OTHER")
                        loss_reason = "OTHER"
                
                loss_stage = parsed.get("loss_stage")
                if loss_stage:
                    try:
                        LossStage(loss_stage)  # Validate enum value
                    except ValueError:
                        logger.warning(f"Invalid loss_stage: {loss_stage}, using QUALIFICATION")
                        loss_stage = "QUALIFICATION"
                
                # Build response
                loss_info = {
                    "detected": True,
                    "loss_reason": loss_reason,
                    "loss_stage": loss_stage,
                    "confidence": min(max(parsed.get("confidence", 0.7), 0.0), 1.0),  # Clamp between 0 and 1
                    "extracted_text": parsed.get("extracted_text", ""),
                    "detailed_reason": parsed.get("detailed_reason"),
                    "client_feedback": parsed.get("client_feedback"),
                }
                
                logger.info(f"Loss intent detected: {loss_info}")
                return loss_info
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON from Gemini response: {e}, answer: {answer}")
                return AISummaryService._detect_loss_intent_regex(processed_content, attendance_status)
            except Exception as e:
                logger.error(f"Exception detecting loss intent with Gemini: {e}", exc_info=True)
                return AISummaryService._detect_loss_intent_regex(processed_content, attendance_status)
                
        except Exception as e:
            logger.error(f"Error in detect_loss_intent: {e}", exc_info=True)
            return None

    @staticmethod
    def detect_sale_intent(
        raw_content: str,
        client_id: uuid.UUID | None = None,
        property_id: uuid.UUID | None = None,
        agent_id: uuid.UUID | None = None,
        attendance_status: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Detect sale intent from raw content using AI.
        
        ⚠️ IMPORTANT: This is ONLY a suggestion. It does NOT change attendance status.
        The attendance remains ACTIVE until the user explicitly confirms the sale.
        
        Analyzes the conversation to identify if a sale/rent was closed,
        extracts sale type, value, payment method, and other details.
        
        Args:
            raw_content: Raw content of the attendance/conversation
            client_id: Optional client ID for context
            property_id: Optional property ID if sale is for a specific property
            agent_id: Optional agent ID
            attendance_status: Current attendance status (if COMPLETED, detection is skipped)
            
        Returns:
            Dictionary with sale information if detected, None otherwise:
            {
                "detected": True,
                "sale_type": "SALE",  # SALE or RENT
                "sale_value": 500000.00,  # Extracted sale value
                "confidence": 0.85,  # Confidence score (0-1)
                "extracted_text": "Cliente fechou a compra por R$ 500.000",
                "payment_method": "FINANCING",  # Payment method mentioned
                "notes": "Venda fechada durante atendimento"
            }
            Or None if no sale intent detected
        """
        # ⚠️ PROTECTION 1: Don't detect sale if attendance is already COMPLETED
        # This prevents multiple detections and annoying popups
        if attendance_status == "COMPLETED":
            logger.info("Skipping sale detection: attendance is already COMPLETED")
            return None
        
        try:
            gemini = AISummaryService._get_gemini_service()
            
            # Truncate content if too large
            processed_content = AISummaryService._truncate_content_intelligently(raw_content, max_chars=50000)
            
            # If Gemini is not configured, use regex-based fallback
            if not gemini.is_configured():
                logger.warning("Gemini API not configured, using regex-based sale detection")
                return AISummaryService._detect_sale_intent_regex(
                    processed_content, attendance_status, property_id
                )
            
            # Build context
            context = ""
            if property_id:
                context += f"\nPROPRIEDADE: ID {property_id}\n"
            if client_id:
                context += f"\nCLIENTE: ID {client_id}\n"
            
            prompt = f"""Você é um assistente especializado em detectar quando uma venda ou aluguel foi fechado.

Analise o seguinte conteúdo de conversa e identifique se o cliente fechou uma venda ou aluguel de imóvel.

{context}

CONTEÚDO DA CONVERSA:
{processed_content}

INSTRUÇÕES:
1. Identifique se há MENÇÃO EXPLÍCITA de venda/aluguel fechado:
   - "fechou", "comprou", "alugou", "vendeu", "aceitou a proposta", "fechamos negócio"
   - "vou comprar", "vou alugar", "aceito", "fechado", "negócio fechado"
   - Menção de valores e condições de pagamento
2. Se detectar venda/aluguel, extraia:
   - TIPO: "SALE" (venda) ou "RENT" (aluguel)
   - VALOR: valor mencionado (apenas números, sem símbolos)
   - FORMA DE PAGAMENTO: se mencionado (CASH, FINANCING, INSTALLMENTS, MIXED)
   - INFORMAÇÕES ADICIONAIS: condições, prazo, etc.
3. VALIDAÇÕES:
   - Valor deve ser um número positivo
   - Tipo deve ser SALE ou RENT
   - Se apenas parte da informação estiver presente, use valores padrão razoáveis
4. Se NÃO houver indicação clara de venda/aluguel fechado, retorne null

Responda APENAS com um JSON válido no formato:
{{
    "detected": true,
    "sale_type": "SALE",
    "sale_value": 500000.00,
    "confidence": 0.85,
    "extracted_text": "Cliente fechou a compra por R$ 500.000",
    "payment_method": "FINANCING",
    "notes": "Venda fechada durante atendimento"
}}

OU, se não detectar venda:
{{
    "detected": false
}}

IMPORTANTE:
- Seja conservador: só detecte venda se houver indicação CLARA de fechamento
- Extraia valores numéricos corretamente (ex: "R$ 500.000" → 500000.00)
- Identifique se é venda (SALE) ou aluguel (RENT)"""

            try:
                result = gemini.chat(
                    message=prompt,
                    system_prompt="Você é um assistente especializado em detectar quando vendas ou aluguéis de imóveis foram fechados. Responda APENAS com JSON válido.",
                )
                
                if result.get("error"):
                    logger.error(f"Error detecting sale intent with Gemini: {result.get('error')}")
                    return AISummaryService._detect_sale_intent_regex(
                        processed_content, attendance_status, property_id
                    )
                
                answer = result.get("answer", "").strip()
                if not answer:
                    return None
                
                # Try to extract JSON from the answer
                import json
                import re
                
                # Remove markdown code blocks if present
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', answer, re.DOTALL)
                if json_match:
                    answer = json_match.group(1)
                else:
                    # Try to find JSON object in the answer
                    json_match = re.search(r'\{.*\}', answer, re.DOTALL)
                    if json_match:
                        answer = json_match.group(0)
                
                parsed = json.loads(answer)
                
                if not parsed.get("detected", False):
                    return None
                
                # Validate sale_type
                from app.sales.models import SaleType, PaymentMethod
                
                sale_type = parsed.get("sale_type", "SALE")
                if sale_type:
                    try:
                        SaleType(sale_type)  # Validate enum value
                    except ValueError:
                        logger.warning(f"Invalid sale_type: {sale_type}, using SALE")
                        sale_type = "SALE"
                
                payment_method = parsed.get("payment_method")
                if payment_method:
                    try:
                        PaymentMethod(payment_method)  # Validate enum value
                    except ValueError:
                        logger.warning(f"Invalid payment_method: {payment_method}, ignoring")
                        payment_method = None
                
                # Build response - incluir property_id do atendimento para pré-preencher o modal
                sale_info = {
                    "detected": True,
                    "sale_type": sale_type,
                    "sale_value": parsed.get("sale_value"),
                    "property_id": property_id,  # Imóvel vinculado ao atendimento
                    "confidence": min(max(parsed.get("confidence", 0.7), 0.0), 1.0),  # Clamp between 0 and 1
                    "extracted_text": parsed.get("extracted_text", ""),
                    "payment_method": payment_method,
                    "notes": parsed.get("notes", "Venda/aluguel detectado durante atendimento"),
                }
                
                logger.info(f"Sale intent detected: {sale_info}")
                return sale_info
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON from Gemini response: {e}, answer: {answer}")
                return AISummaryService._detect_sale_intent_regex(
                    processed_content, attendance_status, property_id
                )
            except Exception as e:
                logger.error(f"Exception detecting sale intent with Gemini: {e}", exc_info=True)
                return AISummaryService._detect_sale_intent_regex(
                    processed_content, attendance_status, property_id
                )
                
        except Exception as e:
            logger.error(f"Error in detect_sale_intent: {e}", exc_info=True)
            return None

    @staticmethod
    def _detect_sale_intent_regex(
        raw_content: str,
        attendance_status: str | None = None,
        property_id: uuid.UUID | None = None,
    ) -> dict[str, Any] | None:
        """
        Fallback regex-based sale intent detection.
        
        ⚠️ IMPORTANT: This is ONLY a suggestion. It does NOT change attendance status.
        
        Args:
            raw_content: Raw content to analyze
            attendance_status: Current attendance status (if COMPLETED, detection is skipped)
            property_id: Property ID from attendance or linked visit for pre-filling sale modal
            
        Returns:
            Sale info dict or None
        """
        # ⚠️ PROTECTION: Don't detect sale if attendance is already COMPLETED
        if attendance_status == "COMPLETED":
            return None
        
        import re
        
        content_lower = raw_content.lower()
        
        # Keywords that indicate sale intent
        sale_keywords = [
            r"fechou",
            r"comprou",
            r"alugou",
            r"vendeu",
            r"aceitou.*proposta",
            r"fechamos.*negócio",
            r"negócio.*fechado",
            r"vou.*comprar",
            r"vou.*alugar",
        ]
        
        has_sale_intent = any(re.search(keyword, content_lower) for keyword in sale_keywords)
        
        if not has_sale_intent:
            return None
        
        # Try to extract sale type
        sale_type = "SALE"
        if re.search(r"alug", content_lower):
            sale_type = "RENT"
        
        # Try to extract value
        value_patterns = [
            r"r\$\s*(\d+(?:\.\d{3})*(?:,\d{2})?)",  # R$ 500.000,00
            r"(\d+(?:\.\d{3})*(?:,\d{2})?)\s*reais",  # 500.000,00 reais
            r"por\s*(\d+(?:\.\d{3})*)",  # por 500000
        ]
        
        sale_value = None
        for pattern in value_patterns:
            match = re.search(pattern, content_lower)
            if match:
                try:
                    value_str = match.group(1).replace('.', '').replace(',', '.')
                    sale_value = float(value_str)
                    break
                except (ValueError, AttributeError):
                    continue
        
        # Try to detect payment method
        payment_method = None
        if re.search(r"(à vista|vista|cash)", content_lower):
            payment_method = "CASH"
        elif re.search(r"(financiamento|financiar)", content_lower):
            payment_method = "FINANCING"
        elif re.search(r"(parcelado|parcelas)", content_lower):
            payment_method = "INSTALLMENTS"
        
        return {
            "detected": True,
            "sale_type": sale_type,
            "sale_value": sale_value,
            "property_id": property_id,  # Imóvel vinculado ao atendimento
            "confidence": 0.6,  # Lower confidence for regex-based
            "extracted_text": raw_content[:200],  # First 200 chars
            "payment_method": payment_method,
            "notes": "Venda/aluguel detectado durante atendimento (detecção automática)",
        }

    @staticmethod
    def _detect_loss_intent_regex(raw_content: str, attendance_status: str | None = None) -> dict[str, Any] | None:
        """
        Fallback regex-based loss intent detection.
        
        ⚠️ IMPORTANT: This is ONLY a suggestion. It does NOT change attendance status.
        
        Args:
            raw_content: Raw content to analyze
            attendance_status: Current attendance status (if LOST, detection is skipped)
            
        Returns:
            Loss info dict or None
        """
        # ⚠️ PROTECTION: Don't detect loss if attendance is already LOST
        if attendance_status == "LOST":
            return None
        import re
        
        content_lower = raw_content.lower()
        
        # Keywords that indicate loss intent
        loss_keywords = [
            r"não\s+quer\s+mais",
            r"desistiu",
            r"não\s+conseguiu",
            r"não\s+vai\s+mais",
            r"cancelou",
            r"não\s+quer\s+continuar",
            r"perdeu\s+interesse",
            r"não\s+está\s+mais\s+interessado",
        ]
        
        has_loss_intent = any(re.search(keyword, content_lower) for keyword in loss_keywords)
        
        if not has_loss_intent:
            return None
        
        # Try to detect reason
        loss_reason = "OTHER"
        if re.search(r"(consórcio|financiamento|crédito|empréstimo)", content_lower):
            loss_reason = "CLIENT_FINANCING_DENIED"
        elif re.search(r"(preço|valor).*alto", content_lower):
            loss_reason = "PRICE_TOO_HIGH"
        elif re.search(r"(orçamento|dinheiro|recursos).*insuficiente", content_lower):
            loss_reason = "BUDGET_INSUFFICIENT"
        elif re.search(r"mudou\s+de\s+ideia", content_lower):
            loss_reason = "CLIENT_CHANGED_MIND"
        
        return {
            "detected": True,
            "loss_reason": loss_reason,
            "loss_stage": "NEGOTIATION",  # Default stage
            "confidence": 0.6,  # Lower confidence for regex-based
            "extracted_text": raw_content[:200],  # First 200 chars
            "detailed_reason": None,
            "client_feedback": None,
        }

    @staticmethod
    def _detect_visit_intent_regex(raw_content: str, property_id: uuid.UUID | None = None) -> dict[str, Any] | None:
        """
        Fallback regex-based visit intent detection.
        
        This is a simpler method that uses regex patterns to detect common visit scheduling phrases.
        Used when Gemini API is not configured.
        
        Args:
            raw_content: Raw content to analyze
            property_id: Optional property ID
            
        Returns:
            Visit info dict or None
        """
        import re
        from datetime import datetime, timedelta
        
        content_lower = raw_content.lower()
        
        # Keywords that indicate visit intent
        visit_keywords = [
            r"quero\s+visitar",
            r"podemos\s+marcar",
            r"agendar\s+visita",
            r"quero\s+ver",
            r"visitar\s+(?:no|na|o)",
            r"marcar\s+visita",  # "marcar visita" (more flexible, matches with or without additional words)
            r"marcar\s+(?:para\s+ver|a\s+visita)",
            r"agendar\s+(?:para|a)",
            r"visita\s+(?:no|na|para)",
        ]
        
        has_visit_intent = any(re.search(keyword, content_lower) for keyword in visit_keywords)
        
        if not has_visit_intent:
            return None
        
        # Try to extract date and time
        # Date patterns: DD/MM/YYYY, DD/MM, "dia X", "amanhã", "segunda-feira", etc.
        date_patterns = [
            r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?",  # DD/MM/YYYY or DD/MM
            r"dia\s+(\d{1,2})",  # "dia 15"
            r"(\d{1,2})\s+de\s+(\w+)",  # "15 de fevereiro"
        ]
        
        # Time patterns: HH:MM, "às X horas", "X horas", "as Xh", etc.
        time_patterns = [
            r"(\d{1,2}):(\d{2})",  # HH:MM
            r"às\s+(\d{1,2})\s*h(?:oras|rs)?",  # "às 14 horas"
            r"as\s+(\d{1,2})\s*h(?:oras|rs)?",  # "as 15h" (lowercase "as")
            r"(\d{1,2})\s*h(?:oras|rs)?",  # "14 horas" or "15h"
        ]
        
        scheduled_at = None
        # IMPORTANTE: Horário mencionado pelo usuário é horário do Brasil (UTC-3)
        from datetime import timezone, timedelta
        brazil_tz = timezone(timedelta(hours=-3))  # UTC-3 (Brasil)
        current_date_utc = datetime.now(timezone.utc)
        current_date_brazil = current_date_utc.astimezone(brazil_tz)
        
        # Try to extract date
        for pattern in date_patterns:
            match = re.search(pattern, content_lower)
            if match:
                try:
                    if pattern == r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?":
                        day = int(match.group(1))
                        month = int(match.group(2))
                        year = int(match.group(3)) if match.group(3) else current_date_brazil.year
                        if year < current_date_brazil.year or (year == current_date_brazil.year and (month < current_date_brazil.month or (month == current_date_brazil.month and day < current_date_brazil.day))):
                            year = current_date_brazil.year + 1 if month < current_date_brazil.month or (month == current_date_brazil.month and day < current_date_brazil.day) else current_date_brazil.year
                        # Criar em horário do Brasil e depois converter para UTC
                        scheduled_at = datetime(year, month, day, 14, 0, tzinfo=brazil_tz)  # Default to 14:00 Brasil
                        scheduled_at = scheduled_at.astimezone(timezone.utc)  # Converter para UTC
                        break
                    elif pattern == r"dia\s+(\d{1,2})":
                        day = int(match.group(1))
                        month = current_date_brazil.month
                        year = current_date_brazil.year
                        if day < current_date_brazil.day:
                            month += 1
                            if month > 12:
                                month = 1
                                year += 1
                        # Criar em horário do Brasil e depois converter para UTC
                        scheduled_at = datetime(year, month, day, 14, 0, tzinfo=brazil_tz)
                        scheduled_at = scheduled_at.astimezone(timezone.utc)  # Converter para UTC
                        break
                except (ValueError, IndexError):
                    continue
        
        # If no date found, check for relative dates
        if not scheduled_at:
            if "amanhã" in content_lower or "amanha" in content_lower:
                scheduled_at_brazil = current_date_brazil + timedelta(days=1)
                scheduled_at_brazil = scheduled_at_brazil.replace(hour=14, minute=0)
                scheduled_at = scheduled_at_brazil.astimezone(timezone.utc)
            elif "hoje" in content_lower:
                scheduled_at_brazil = current_date_brazil.replace(hour=14, minute=0)
                if scheduled_at_brazil < current_date_brazil:
                    scheduled_at_brazil = scheduled_at_brazil + timedelta(days=1)
                scheduled_at = scheduled_at_brazil.astimezone(timezone.utc)
            else:
                # Default to tomorrow if visit intent detected but no date
                scheduled_at_brazil = current_date_brazil + timedelta(days=1)
                scheduled_at_brazil = scheduled_at_brazil.replace(hour=14, minute=0)
                scheduled_at = scheduled_at_brazil.astimezone(timezone.utc)
        
        # Try to extract time (horário mencionado é horário do Brasil)
        if scheduled_at:
            # Converter para horário do Brasil para ajustar a hora
            scheduled_at_brazil = scheduled_at.astimezone(brazil_tz)
            
            for pattern in time_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    try:
                        if pattern == r"(\d{1,2}):(\d{2})":
                            hour = int(match.group(1))
                            minute = int(match.group(2))
                        else:
                            hour = int(match.group(1))
                            minute = 0
                        
                        if 8 <= hour < 20:
                            # Ajustar hora no horário do Brasil
                            scheduled_at_brazil = scheduled_at_brazil.replace(hour=hour, minute=minute)
                            # Converter de volta para UTC
                            scheduled_at = scheduled_at_brazil.astimezone(timezone.utc)
                        break
                    except (ValueError, IndexError):
                        continue
        
        # Validate: date cannot be in the past (comparar no timezone do Brasil)
        if scheduled_at:
            scheduled_at_brazil = scheduled_at.astimezone(brazil_tz)
            
            if scheduled_at_brazil >= current_date_brazil:
                # Formatar data/hora no horário do Brasil para exibição
                scheduled_at_brazil = scheduled_at.astimezone(brazil_tz)
                return {
                    "detected": True,
                    "scheduled_at": scheduled_at.isoformat(),  # UTC para armazenar
                    "date": scheduled_at_brazil.strftime("%d/%m/%Y"),  # Data no horário do Brasil
                    "time": scheduled_at_brazil.strftime("%H:%M"),  # Hora no horário do Brasil
                    "confidence": 0.6,  # Lower confidence for regex-based detection
                    "extracted_text": f"Visita detectada para {scheduled_at_brazil.strftime('%d/%m/%Y às %H:%M')}",
                    "property_id": str(property_id) if property_id else None,
                    "notes": "Visita agendada durante atendimento (detecção automática)",
                }
        
        return None

    @staticmethod
    def detect_property_mention(
        raw_content: str,
        db: Session | None = None,
        current_property_id: uuid.UUID | None = None,
    ) -> dict[str, Any] | None:
        """
        Detect if a specific property is mentioned in the raw_content.
        
        Analyzes the conversation to identify if the client is referring to a specific property
        by code, address, or unique characteristics. If a property is already linked, it will
        only change if a different property is explicitly mentioned.
        
        Args:
            raw_content: Raw content of the attendance/conversation
            db: Database session (required for property lookup)
            current_property_id: Currently linked property_id (if any)
            
        Returns:
            Dictionary with property information if detected, None otherwise:
            {
                "detected": True,
                "property_id": uuid.UUID,
                "property_code": str,
                "confidence": 0.85,
                "detection_method": "code" | "address" | "characteristics" | "confirmation",
                "extracted_text": "Cliente mencionou código ABC123",
                "is_confirmation": False,  # True if client confirmed/decided on this property
            }
            Or None if no specific property detected
        """
        if not db:
            return None
        
        try:
            gemini = AISummaryService._get_gemini_service()
            from app.properties.repository import PropertyRepository
            
            property_repo = PropertyRepository(db)
            
            # Truncate content if too large
            processed_content = AISummaryService._truncate_content_intelligently(raw_content, max_chars=50000)
            
            # If Gemini is not configured, use regex-based fallback
            if not gemini.is_configured():
                logger.warning("Gemini API not configured, using regex-based property detection")
                return AISummaryService._detect_property_mention_regex(
                    processed_content, property_repo, current_property_id
                )
            
            # Get all published properties for context (limit to avoid too much data)
            all_properties = property_repo.get_all(
                skip=0,
                limit=1000,  # Get up to 1000 properties for matching
            )
            
            if not all_properties:
                return None
            
            # Build property context for AI
            properties_context = []
            for prop in all_properties[:100]:  # Limit to 100 for prompt size
                prop_info = f"Código: {prop.code}, Título: {prop.title}"
                if prop.city:
                    prop_info += f", Cidade: {prop.city}"
                if prop.neighborhood:
                    prop_info += f", Bairro: {prop.neighborhood}"
                if prop.street:
                    prop_info += f", Rua: {prop.street}"
                if prop.number:
                    prop_info += f", Número: {prop.number}"
                if prop.bedrooms:
                    prop_info += f", {prop.bedrooms} quartos"
                if prop.property_type:
                    prop_info += f", Tipo: {prop.property_type.value}"
                properties_context.append(prop_info)
            
            properties_list = "\n".join(properties_context)
            
            # Build context about current property if any
            current_property_context = ""
            if current_property_id:
                current_prop = property_repo.get_by_id(current_property_id)
                if current_prop:
                    current_property_context = f"""
IMÓVEL ATUALMENTE VINCULADO:
- Código: {current_prop.code}
- Título: {current_prop.title}
- Cidade: {current_prop.city or 'Não informada'}
- Bairro: {current_prop.neighborhood or 'Não informado'}
- Endereço: {current_prop.street or ''} {current_prop.number or ''}

IMPORTANTE: Se o cliente confirmar ou decidir por este imóvel (ex: "quero esse", "vou com esse", "esse mesmo"), 
retorne o property_id atual com is_confirmation=true. Só mude o property_id se um IMÓVEL DIFERENTE for mencionado.
"""
            
            prompt = f"""Você é um assistente especializado em identificar imóveis específicos mencionados em conversas imobiliárias.

Analise o seguinte conteúdo de conversa e identifique se o cliente está se referindo a um IMÓVEL ESPECÍFICO do catálogo.

IMÓVEIS DISPONÍVEIS:
{properties_list}

{current_property_context}

CONTEÚDO DA CONVERSA:
{processed_content}

INSTRUÇÕES:
1. Identifique se há menção a um IMÓVEL ESPECÍFICO (não apenas preferências genéricas)
2. Sinais de imóvel específico:
   - Código do imóvel mencionado (ex: "código ABC123", "imóvel 123", "ref 456")
   - Endereço específico (rua, número, bairro)
   - Características únicas que identifiquem um imóvel específico
   - Confirmação/decisaão sobre um imóvel (ex: "quero esse", "vou com esse", "esse mesmo", "decidi por esse")
3. Se houver imóvel atualmente vinculado e o cliente confirmar/decidir por ele, retorne esse property_id com is_confirmation=true
4. Só mude o property_id se um IMÓVEL DIFERENTE for mencionado
5. Se não houver menção clara a imóvel específico, retorne null

Responda APENAS com um JSON válido no formato:
{{
    "detected": true,
    "property_id": "uuid-do-imovel",
    "property_code": "ABC123",
    "confidence": 0.85,
    "detection_method": "code" | "address" | "characteristics" | "confirmation",
    "extracted_text": "Cliente mencionou código ABC123",
    "is_confirmation": false
}}

OU, se não detectar imóvel específico:
{{
    "detected": false
}}

IMPORTANTE:
- Use o código do imóvel para identificar o property_id correto
- Se o cliente disser "quero esse", "esse mesmo", "vou com esse", considere como confirmação do imóvel atual
- Só retorne detected=true se tiver CERTEZA de qual imóvel específico está sendo mencionado"""

            try:
                result = gemini.chat(
                    message=prompt,
                    system_prompt="Você é um assistente especializado em identificar imóveis específicos mencionados em conversas imobiliárias. Responda APENAS com JSON válido.",
                )
                
                if result.get("error"):
                    logger.error(f"Error detecting property mention with Gemini: {result.get('error')}")
                    return AISummaryService._detect_property_mention_regex(
                        processed_content, property_repo, current_property_id
                    )
                
                answer = result.get("answer", "").strip()
                if not answer:
                    return None
                
                # Try to extract JSON from the answer
                import json
                import re
                
                # Remove markdown code blocks if present
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', answer, re.DOTALL)
                if json_match:
                    answer = json_match.group(1)
                else:
                    # Try to find JSON object in the answer
                    json_match = re.search(r'\{.*\}', answer, re.DOTALL)
                    if json_match:
                        answer = json_match.group(0)
                
                parsed = json.loads(answer)
                
                if not parsed.get("detected", False):
                    return None
                
                property_code = parsed.get("property_code")
                if not property_code:
                    return None
                
                # Find property by code
                property_found = property_repo.get_by_code(property_code.upper().strip())
                if not property_found:
                    logger.warning(f"Property code {property_code} mentioned but not found in database")
                    return None
                
                # Check if this is a confirmation of current property
                is_confirmation = parsed.get("is_confirmation", False)
                if is_confirmation and current_property_id:
                    if str(property_found.id) == str(current_property_id):
                        # Client confirmed current property
                        return {
                            "detected": True,
                            "property_id": property_found.id,
                            "property_code": property_found.code,
                            "confidence": min(max(parsed.get("confidence", 0.9), 0.0), 1.0),
                            "detection_method": "confirmation",
                            "extracted_text": parsed.get("extracted_text", ""),
                            "is_confirmation": True,
                        }
                
                # Check if different property was mentioned
                if current_property_id and str(property_found.id) == str(current_property_id):
                    # Same property, but not explicit confirmation - don't change
                    return None
                
                # New or different property detected
                return {
                    "detected": True,
                    "property_id": property_found.id,
                    "property_code": property_found.code,
                    "confidence": min(max(parsed.get("confidence", 0.7), 0.0), 1.0),
                    "detection_method": parsed.get("detection_method", "code"),
                    "extracted_text": parsed.get("extracted_text", ""),
                    "is_confirmation": is_confirmation,
                }
                    
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON from Gemini response: {e}, answer: {answer}")
                return AISummaryService._detect_property_mention_regex(
                    processed_content, property_repo, current_property_id
                )
            except Exception as e:
                logger.error(f"Exception detecting property mention with Gemini: {e}", exc_info=True)
                return AISummaryService._detect_property_mention_regex(
                    processed_content, property_repo, current_property_id
                )
                
        except Exception as e:
            logger.error(f"Error in detect_property_mention: {e}", exc_info=True)
            return None

    @staticmethod
    def _detect_property_mention_regex(
        raw_content: str,
        property_repo,
        current_property_id: uuid.UUID | None = None,
    ) -> dict[str, Any] | None:
        """
        Fallback regex-based property mention detection.
        
        This is a simpler method that uses regex patterns to detect property codes.
        Used when Gemini API is not configured.
        
        Args:
            raw_content: Raw content to analyze
            property_repo: PropertyRepository instance
            current_property_id: Currently linked property_id (if any)
            
        Returns:
            Property info dict or None
        """
        import re
        
        content = raw_content
        
        # Look for property codes (patterns like "código ABC123", "imóvel 123", "ref 456", etc.)
        code_patterns = [
            r"(?:código|code|ref|referência|imóvel)\s*[:\-]?\s*([A-Z0-9]{3,20})",
            r"imóvel\s+([A-Z0-9]{3,20})",
            r"propriedade\s+([A-Z0-9]{3,20})",
        ]
        
        for pattern in code_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                code = match.group(1).upper().strip()
                try:
                    property_found = property_repo.get_by_code(code)
                    if property_found:
                        return {
                            "detected": True,
                            "property_id": property_found.id,
                            "property_code": property_found.code,
                            "confidence": 0.6,
                            "detection_method": "code",
                            "extracted_text": f"Cliente mencionou código {code}",
                            "is_confirmation": False,
                        }
                except Exception:
                    continue
        
        # Look for confirmation phrases
        confirmation_patterns = [
            r"(?:quero|vou com|decidi|escolhi|esse mesmo|esse|este mesmo|este)\s+(?:esse|este|esse imóvel|este imóvel|esse apartamento|este apartamento|essa casa|esta casa)",
            r"(?:confirmo|confirmado|decidido|escolhido)\s+(?:esse|este|esse imóvel|este imóvel)",
        ]
        
        for pattern in confirmation_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                if current_property_id:
                    current_prop = property_repo.get_by_id(current_property_id)
                    if current_prop:
                        return {
                            "detected": True,
                            "property_id": current_prop.id,
                            "property_code": current_prop.code,
                            "confidence": 0.7,
                            "detection_method": "confirmation",
                            "extracted_text": "Cliente confirmou/decidiu pelo imóvel",
                            "is_confirmation": True,
                        }
        
        return None


