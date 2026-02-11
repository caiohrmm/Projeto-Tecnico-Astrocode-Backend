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

            # Generate AI summary using Gemini API
            summary_text = AISummaryService._generate_summary_text(attendance.raw_content)
            key_points = AISummaryService._extract_key_points(raw_content)
            detected_intent = AISummaryService._detect_intent(raw_content)
            interest_type = AISummaryService._detect_interest_type(raw_content)
            budget_range = AISummaryService._detect_budget(raw_content)
            urgency_level = AISummaryService._detect_urgency(raw_content)
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

            # Generate property recommendations if no property is already assigned
            # Always try to recommend if we have client preferences, even if no property is linked
            recommended_properties: list[uuid.UUID] | None = None
            if db and (not attendance.property_id or interest_type or city or detected_property_type or budget_range.get("min") or budget_range.get("max")):
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
    def _generate_summary_text(raw_content: str) -> str:
        """
        Generate summary text from raw content using Gemini API.
        
        Automatically truncates content if it exceeds 50k characters to:
        - Avoid excessive API costs
        - Maintain AI context window
        - Prioritize recent conversations while keeping initial context
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
        
        prompt = f"""Você é um assistente especializado em análise de atendimentos imobiliários.

Analise o seguinte conteúdo de atendimento e gere um resumo profissional, conciso e útil em português brasileiro.

DATA ATUAL: {current_date}

REGRAS IMPORTANTES:
- NÃO copie o conteúdo original palavra por palavra
- Crie um resumo objetivo destacando os pontos principais
- Foque em: interesse do cliente, preferências (tipo de imóvel, localização, orçamento), urgência, sentimentos
- Use linguagem profissional mas acessível
- Seja específico sobre valores, localizações e preferências mencionadas
- Máximo de 200 palavras

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
        """Detect intent from raw content."""
        content_lower = raw_content.lower()

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
            return DetectedIntent.FOLLOW_UP
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

        # Look for numbers that might be prices (R$, valores, etc.)
        numbers = re.findall(r"[\d.]+", raw_content.replace(",", "."))
        prices = []

        for num_str in numbers:
            try:
                num = float(num_str)
                # Assume prices are between 50k and 10M
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
        """Detect urgency level from raw content."""
        content_lower = raw_content.lower()

        # Immediate urgency indicators
        if any(word in content_lower for word in ["imediato", "urgente", "hoje", "agora", "rápido", "já", "imediatamente"]):
            return UrgencyLevel.IMMEDIATE
        
        # High urgency: next week, few days, soon
        if any(word in content_lower for word in [
            "semana que vem", "próxima semana", "próximo", "logo", "breve", "em breve",
            "daqui alguns dias", "daqui poucos dias", "nos próximos dias", "essa semana"
        ]):
            return UrgencyLevel.HIGH
        
        # Medium urgency: thinking, evaluating, but with some timeline
        if any(word in content_lower for word in ["pensando", "avaliando", "considerando", "mês que vem", "próximo mês"]):
            return UrgencyLevel.MEDIUM
        
        # Low urgency: no clear timeline or distant future
        if any(word in content_lower for word in ["futuro", "depois", "mais tarde", "sem pressa", "sem urgência"]):
            return UrgencyLevel.LOW
        
        # Default to medium if there's any indication of interest
        if any(word in content_lower for word in ["interesse", "gostaria", "quero", "preciso", "buscar", "procurar"]):
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
        if detected_intent == DetectedIntent.SCHEDULE_VISIT:
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
        """Extract city name from raw content."""
        content_lower = raw_content.lower()
        
        # Try to find patterns like "em [city]", "na cidade de [city]", etc.
        # This approach is more flexible and catches any city name
        patterns = [
            # "em Manduri", "em São Paulo", etc.
            r"(?:em|na|no|para)\s+([A-Z][a-zà-ú]+(?:\s+(?:do|da|de|dos|das)?\s*[A-Z][a-zà-ú]+)*)",
            # "cidade de Manduri"
            r"cidade\s+(?:de|do|da)?\s*([A-Z][a-zà-ú]+(?:\s+[A-Za-zà-ú]+)*)",
            # "morar em Manduri"
            r"morar\s+em\s+([A-Z][a-zà-ú]+(?:\s+[A-Za-zà-ú]+)*)",
            # "imóvel em Manduri"
            r"imóvel\s+em\s+([A-Z][a-zà-ú]+(?:\s+[A-Za-zà-ú]+)*)",
            # "casa em Manduri"
            r"(?:casa|apartamento|terreno)\s+em\s+([A-Z][a-zà-ú]+(?:\s+[A-Za-zà-ú]+)*)",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, raw_content)
            if matches:
                for match in matches:
                    # Clean up the match
                    city = match.strip()
                    # Skip common non-city words
                    skip_words = ["casa", "apartamento", "imóvel", "terreno", "comprar", 
                                  "alugar", "vender", "buscar", "procurar", "quer"]
                    if city.lower() not in skip_words and len(city) > 2:
                        # City names are usually 1-3 words
                        if len(city.split()) <= 4:
                            return city
        
        # Also check for cities mentioned with lowercase after prepositions
        lowercase_patterns = [
            r"(?:em|na|no|para)\s+([a-zà-ú]+(?:\s+(?:do|da|de|dos|das)?\s*[a-zà-ú]+)*)",
        ]
        
        for pattern in lowercase_patterns:
            matches = re.findall(pattern, content_lower)
            if matches:
                for match in matches:
                    city = match.strip()
                    skip_words = ["casa", "apartamento", "imóvel", "terreno", "comprar", 
                                  "alugar", "vender", "buscar", "procurar", "quer", "uma", "um",
                                  "breve", "geral", "qualquer", "lugar", "algum"]
                    if city.lower() not in skip_words and len(city) > 3:
                        if len(city.split()) <= 3:
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
            
            # Return list of property IDs
            property_ids = [prop.id for prop in properties]
            logger.info(f"Found {len(property_ids)} recommended properties for client {client_id}")
            return property_ids
            
        except Exception as e:
            logger.error(f"Error recommending properties: {e}", exc_info=True)
            return None


