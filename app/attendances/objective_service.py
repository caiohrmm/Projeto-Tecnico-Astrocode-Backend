"""Service for detecting and comparing attendance objectives."""

import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.gemini_service import GeminiService
from app.attendances.models import Attendance, AttendanceStatus
from app.clients.models import Client, InterestType, PropertyType

logger = logging.getLogger(__name__)


class AttendanceObjective(BaseModel):
    """
    Structured representation of an attendance objective.
    
    This is the internal domain model for objectives, used for logic and comparison.
    The database still stores a human-readable string, but internally we use this
    structured format for robust comparison and decision-making.
    """
    
    intent_type: Optional[InterestType] = Field(
        None,
        description="Type of interest: BUY, RENT, SELL, or INVEST",
    )
    property_type: Optional[PropertyType] = Field(
        None,
        description="Type of property: HOUSE, APARTMENT, LAND, COMMERCIAL, or RURAL",
    )
    city: Optional[str] = Field(
        None,
        description="City name (normalized, e.g., 'SAO_PAULO' or 'São Paulo')",
    )
    additional_context: Optional[str] = Field(
        None,
        description="Additional context or details about the objective",
    )
    
    def to_human_readable(self) -> str:
        """
        Convert structured objective to human-readable string.
        
        Returns:
            Human-readable objective string for storage/display
        """
        parts = []
        
        # Intent type
        if self.intent_type:
            intent_map = {
                InterestType.BUY: "Comprar",
                InterestType.RENT: "Alugar",
                InterestType.SELL: "Vender",
                InterestType.INVEST: "Investir",
            }
            # Handle both enum and string values
            if isinstance(self.intent_type, str):
                # If it's a string, try to map it
                intent_str = self.intent_type.upper()
                reverse_map = {
                    "BUY": "Comprar",
                    "RENT": "Alugar",
                    "SELL": "Vender",
                    "INVEST": "Investir",
                }
                parts.append(reverse_map.get(intent_str, self.intent_type))
            else:
                # If it's an enum, use the map
                parts.append(intent_map.get(self.intent_type, self.intent_type.value))
        
        # Property type
        if self.property_type:
            property_map = {
                PropertyType.HOUSE: "casa",
                PropertyType.APARTMENT: "apartamento",
                PropertyType.LAND: "terreno",
                PropertyType.COMMERCIAL: "imóvel comercial",
                PropertyType.RURAL: "imóvel rural",
            }
            # Handle both enum and string values
            if isinstance(self.property_type, str):
                # If it's a string, try to map it
                property_str = self.property_type.upper()
                reverse_map = {
                    "HOUSE": "casa",
                    "APARTMENT": "apartamento",
                    "LAND": "terreno",
                    "COMMERCIAL": "imóvel comercial",
                    "RURAL": "imóvel rural",
                }
                parts.append(reverse_map.get(property_str, self.property_type.lower()))
            else:
                # If it's an enum, use the map
                parts.append(property_map.get(self.property_type, self.property_type.value.lower()))
        
        # City
        if self.city:
            parts.append(f"em {self.city}")
        
        # Additional context
        if self.additional_context:
            parts.append(f"({self.additional_context})")
        
        if parts:
            return " ".join(parts)
        
        return "Objetivo não definido"
    
    def is_valid(self) -> bool:
        """
        Check if objective has minimum required information.
        
        Returns:
            True if objective has at least intent_type or city
        """
        return self.intent_type is not None or self.city is not None
    
    class Config:
        """Pydantic config."""
        use_enum_values = True


class AttendanceObjectiveService:
    """
    Service for detecting and comparing attendance objectives.
    
    An objective represents the clear goal of an interaction cycle.
    Examples:
    - "Purchase residential property in São Paulo"
    - "Rent apartment in Rio de Janeiro"
    - "Investment property in Belo Horizonte"
    """

    # Days of inactivity to consider a reactivation
    REACTIVATION_THRESHOLD_DAYS = 30

    @staticmethod
    def detect_objective(
        raw_content: str,
        client_data: Optional[dict] = None,
    ) -> Tuple[Optional[AttendanceObjective], Optional[str]]:
        """
        Detect the objective of an attendance from raw content.
        
        Uses AI to extract structured objective fields and generates a human-readable string.
        
        Args:
            raw_content: Raw content of the attendance
            client_data: Optional client data for context
            
        Returns:
            Tuple of (structured_objective, human_readable_string)
            Both can be None if objective cannot be determined
        """
        try:
            gemini = GeminiService()
            
            # Build context from client data if available
            context = ""
            if client_data:
                context = f"""
CONTEXTO DO CLIENTE:
- Tipo de interesse atual: {client_data.get('current_interest_type', 'Não definido')}
- Cidade de interesse atual: {client_data.get('current_city_interest', 'Não definida')}
- Tipo de imóvel: {client_data.get('current_property_type', 'Não definido')}
"""
            
            prompt = f"""Você é um especialista em análise de objetivos de atendimento imobiliário.

Analise o seguinte conteúdo de atendimento e extraia o OBJETIVO PRINCIPAL do cliente em formato JSON estruturado.

{context}

CONTEÚDO DO ATENDIMENTO:
{raw_content}

REGRAS:
1. Extraia os campos estruturados: intent_type, property_type, city, additional_context
2. intent_type deve ser: "BUY", "RENT", "SELL", ou "INVEST" (ou null se não detectado)
3. property_type deve ser: "HOUSE", "APARTMENT", "LAND", "COMMERCIAL", ou "RURAL" (ou null se não detectado)
4. city deve ser o nome da cidade normalizado (ex: "São Paulo", "Rio de Janeiro") ou null
5. additional_context pode conter detalhes adicionais ou null
6. Se não houver informações suficientes, retorne todos os campos como null

Responda APENAS com um JSON válido no formato:
{{
    "intent_type": "BUY" | "RENT" | "SELL" | "INVEST" | null,
    "property_type": "HOUSE" | "APARTMENT" | "LAND" | "COMMERCIAL" | "RURAL" | null,
    "city": "nome da cidade" | null,
    "additional_context": "contexto adicional" | null
}}"""

            if gemini.is_configured():
                result = gemini.chat(
                    message=prompt,
                    system_prompt="Você é um especialista em análise de objetivos de atendimento imobiliário. Responda APENAS com JSON válido, sem explicações adicionais.",
                )
                
                answer = result.get("answer", "").strip()
                
                # Try to parse JSON from response
                try:
                    # Extract JSON from response (might have markdown code blocks)
                    json_match = re.search(r'\{[^{}]*\}', answer, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        objective_dict = json.loads(json_str)
                        
                        # Build structured objective
                        structured = AttendanceObjective(
                            intent_type=objective_dict.get("intent_type"),
                            property_type=objective_dict.get("property_type"),
                            city=objective_dict.get("city"),
                            additional_context=objective_dict.get("additional_context"),
                        )
                        
                        # Generate human-readable string
                        human_readable = structured.to_human_readable()
                        
                        if structured.is_valid():
                            return structured, human_readable
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    logger.warning(f"Failed to parse JSON from Gemini response: {e}. Response: {answer}")
            
            # Fallback to keyword matching
            logger.warning("Gemini API not configured or failed, using fallback objective detection")
            structured, human_readable = AttendanceObjectiveService._detect_objective_fallback(raw_content, client_data)
            return structured, human_readable
                
        except Exception as e:
            logger.error(f"Error detecting objective: {e}", exc_info=True)
            structured, human_readable = AttendanceObjectiveService._detect_objective_fallback(raw_content, client_data)
            return structured, human_readable

    @staticmethod
    def _detect_objective_fallback(
        raw_content: str,
        client_data: Optional[dict] = None,
    ) -> Tuple[Optional[AttendanceObjective], Optional[str]]:
        """
        Fallback method to detect objective using keyword matching.
        
        Args:
            raw_content: Raw content of the attendance
            client_data: Optional client data for context
            
        Returns:
            Tuple of (structured_objective, human_readable_string)
        """
        content_lower = raw_content.lower()
        
        # Detect interest type
        intent_type = None
        if any(word in content_lower for word in ["comprar", "compra", "adquirir"]):
            intent_type = InterestType.BUY
        elif any(word in content_lower for word in ["alugar", "aluguel", "locação"]):
            intent_type = InterestType.RENT
        elif any(word in content_lower for word in ["investir", "investimento"]):
            intent_type = InterestType.INVEST
        elif any(word in content_lower for word in ["vender", "venda"]):
            intent_type = InterestType.SELL
        
        # Detect property type
        property_type = None
        if any(word in content_lower for word in ["apartamento", "apto", "ap"]):
            property_type = PropertyType.APARTMENT
        elif any(word in content_lower for word in ["casa", "residencial"]):
            property_type = PropertyType.HOUSE
        elif any(word in content_lower for word in ["comercial", "loja", "escritório"]):
            property_type = PropertyType.COMMERCIAL
        elif any(word in content_lower for word in ["terreno", "lote"]):
            property_type = PropertyType.LAND
        elif any(word in content_lower for word in ["rural", "fazenda", "sítio"]):
            property_type = PropertyType.RURAL
        
        # Detect city (simple keyword matching - can be improved)
        city = None
        # Common Brazilian cities with normalized names
        city_mapping = {
            "são paulo": "São Paulo",
            "rio de janeiro": "Rio de Janeiro",
            "belo horizonte": "Belo Horizonte",
            "curitiba": "Curitiba",
            "porto alegre": "Porto Alegre",
            "brasília": "Brasília",
            "salvador": "Salvador",
            "recife": "Recife",
            "fortaleza": "Fortaleza",
            "manaus": "Manaus",
        }
        
        for city_key, city_name in city_mapping.items():
            if city_key in content_lower:
                city = city_name
                break
        
        # Use client data if available and not found in content
        if not city and client_data and client_data.get('current_city_interest'):
            city = client_data.get('current_city_interest')
        
        # Build structured objective
        structured = AttendanceObjective(
            intent_type=intent_type,
            property_type=property_type,
            city=city,
            additional_context=None,
        )
        
        # Generate human-readable string
        human_readable = structured.to_human_readable() if structured.is_valid() else None
        
        return structured if structured.is_valid() else None, human_readable

    @staticmethod
    def compare_objectives(
        objective1: Optional[AttendanceObjective],
        objective2: Optional[AttendanceObjective],
    ) -> bool:
        """
        Compare two structured objectives to determine if they represent the same goal.
        
        **Decision Logic:**
        - Returns `True` if objectives are similar enough to continue the same cycle
        - Returns `False` if objectives differ significantly (new cycle needed)
        
        **Comparison Rules (strict matching):**
        1. **intent_type**: Must match exactly if both are present
           - BUY ≠ RENT ≠ INVEST ≠ SELL
           - If one is None, comparison is skipped (flexible)
        
        2. **city**: Must match exactly (case-insensitive, normalized)
           - "São Paulo" == "são paulo" == "SAO PAULO"
           - If one is None, comparison is skipped (flexible)
        
        3. **property_type**: Can differ (flexible matching)
           - Client might refine preference within same cycle
           - Example: "apartment" → "house" in same city with same intent = same cycle
        
        **Examples:**
        - BUY + São Paulo + Apartment vs BUY + São Paulo + House → True (same cycle)
        - BUY + São Paulo vs RENT + São Paulo → False (different cycle)
        - BUY + São Paulo vs BUY + Rio de Janeiro → False (different cycle)
        - BUY + São Paulo vs None + São Paulo → True (flexible, continues cycle)
        
        **Note:** This is a deterministic comparison based on structured fields,
        not semantic similarity. For semantic similarity, use AI-based comparison.
        
        Args:
            objective1: First structured objective
            objective2: Second structured objective
            
        Returns:
            True if objectives are similar (same cycle), False if different (new cycle needed)
        """
        if not objective1 or not objective2:
            # If either is None, consider them different (conservative approach)
            return False
        
        # Compare intent_type (must match if both present)
        if objective1.intent_type and objective2.intent_type:
            if objective1.intent_type != objective2.intent_type:
                return False
        
        # Compare city (must match if both present)
        if objective1.city and objective2.city:
            # Normalize city names for comparison (case-insensitive, strip whitespace)
            city1 = objective1.city.strip().lower()
            city2 = objective2.city.strip().lower()
            if city1 != city2:
                return False
        
        # Property type can differ - client might refine preference within same cycle
        # (e.g., from "apartment" to "house" in same city with same intent)
        
        # If we get here, objectives are similar enough to be the same cycle
        return True
    
    @staticmethod
    def parse_objective_from_string(objective_string: Optional[str]) -> Optional[AttendanceObjective]:
        """
        Parse a human-readable objective string into structured format.
        
        This is used for backward compatibility with existing database records.
        
        Args:
            objective_string: Human-readable objective string from database
            
        Returns:
            Structured objective or None if cannot be parsed
        """
        if not objective_string:
            return None
        
        content_lower = objective_string.lower()
        
        # Extract intent_type
        intent_type = None
        if any(word in content_lower for word in ["comprar", "compra"]):
            intent_type = InterestType.BUY
        elif any(word in content_lower for word in ["alugar", "aluguel"]):
            intent_type = InterestType.RENT
        elif any(word in content_lower for word in ["investir", "investimento"]):
            intent_type = InterestType.INVEST
        elif any(word in content_lower for word in ["vender", "venda"]):
            intent_type = InterestType.SELL
        
        # Extract property_type
        property_type = None
        if any(word in content_lower for word in ["apartamento", "apto"]):
            property_type = PropertyType.APARTMENT
        elif any(word in content_lower for word in ["casa", "residencial"]):
            property_type = PropertyType.HOUSE
        elif any(word in content_lower for word in ["comercial"]):
            property_type = PropertyType.COMMERCIAL
        elif any(word in content_lower for word in ["terreno", "lote"]):
            property_type = PropertyType.LAND
        elif any(word in content_lower for word in ["rural"]):
            property_type = PropertyType.RURAL
        
        # Extract city (from "em [city]" pattern)
        city_match = re.search(r"em\s+([a-záàâãéêíóôõúç\s]+)", content_lower)
        city = None
        if city_match:
            city = city_match.group(1).strip().title()
        
        structured = AttendanceObjective(
            intent_type=intent_type,
            property_type=property_type,
            city=city,
            additional_context=None,
        )
        
        return structured if structured.is_valid() else None

    @staticmethod
    def should_create_new_attendance(
        client_id: uuid.UUID,
        new_objective: Optional[AttendanceObjective],
        existing_active_attendance: Optional[Attendance],
        db: Session,
        raw_content: Optional[str] = None,
    ) -> bool:
        """
        Determine if a new attendance should be created or existing one should be updated.
        
        Uses structured objective comparison for robust decision-making.
        
        Rules for creating NEW attendance:
        - Objective changed significantly (different interest type, different city)
        - Client reactivated after long inactivity (REACTIVATION_THRESHOLD_DAYS)
        - Previous attendance was closed (COMPLETED, LOST, ABANDONED)
        
        Rules for UPDATING existing attendance:
        - Same objective (follow-up, negotiation, multiple visits, time to decide)
        - Refining preferences within same goal (e.g., property type change)
        
        Args:
            client_id: Client UUID
            new_objective: New structured objective detected from content
            existing_active_attendance: Existing active attendance (if any)
            db: Database session
            raw_content: Raw content for additional analysis
            
        Returns:
            True if should create new attendance, False if should update existing
        """
        # If no existing active attendance, create new
        if not existing_active_attendance:
            return True
        
        # If existing attendance is not ACTIVE, create new
        if existing_active_attendance.status != AttendanceStatus.ACTIVE:
            return True
        
        # If no new objective detected, update existing (might be follow-up)
        if not new_objective:
            return False
        
        # Parse existing objective from string (backward compatibility)
        existing_objective_string = existing_active_attendance.objective
        existing_objective = None
        if existing_objective_string:
            existing_objective = AttendanceObjectiveService.parse_objective_from_string(existing_objective_string)
        
        # If we can't parse existing objective, compare by string (fallback)
        if not existing_objective:
            # If existing has no objective but new one does, update existing with new objective
            if new_objective:
                logger.info(
                    f"Existing attendance has no objective, updating with new objective for client {client_id}."
                )
                return False
            return False
        
        # Compare structured objectives
        if AttendanceObjectiveService.compare_objectives(existing_objective, new_objective):
            # Objectives are similar - update existing
            logger.info(
                f"Objectives are similar for client {client_id}. Updating existing attendance."
            )
            return False
        
        # Objectives are different - check if it's a significant change
        
        # If intent_type changed, create new
        if existing_objective.intent_type and new_objective.intent_type:
            if existing_objective.intent_type != new_objective.intent_type:
                logger.info(
                    f"Intent type changed from {existing_objective.intent_type} to {new_objective.intent_type} "
                    f"for client {client_id}. Creating new attendance."
                )
                return True
        
        # If city changed, create new
        if existing_objective.city and new_objective.city:
            city1 = existing_objective.city.strip().lower()
            city2 = new_objective.city.strip().lower()
            if city1 != city2:
                logger.info(
                    f"City changed from {existing_objective.city} to {new_objective.city} "
                    f"for client {client_id}. Creating new attendance."
                )
                return True
        
        # Check for reactivation (long inactivity)
        if existing_active_attendance.ended_at:
            days_since_ended = (datetime.utcnow() - existing_active_attendance.ended_at.replace(tzinfo=None)).days
            if days_since_ended >= AttendanceObjectiveService.REACTIVATION_THRESHOLD_DAYS:
                logger.info(
                    f"Client {client_id} reactivated after {days_since_ended} days. Creating new attendance."
                )
                return True
        elif existing_active_attendance.updated_at:
            days_since_update = (datetime.utcnow() - existing_active_attendance.updated_at.replace(tzinfo=None)).days
            if days_since_update >= AttendanceObjectiveService.REACTIVATION_THRESHOLD_DAYS:
                logger.info(
                    f"Client {client_id} reactivated after {days_since_update} days of inactivity. Creating new attendance."
                )
                return True
        
        # If we get here, objectives are different but not significantly different
        # (e.g., property type refinement, same city/interest)
        # Update existing attendance
        logger.info(
            f"Objective changed but not significantly for client {client_id}. "
            f"Updating existing attendance. Old: {existing_objective.to_human_readable()}, "
            f"New: {new_objective.to_human_readable()}"
        )
        return False

