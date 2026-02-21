"""Visibility score calculation for properties.

The score (0-100) measures how complete and attractive a property listing is,
directly impacting its position in property listings. Higher scores rank first.
"""

from decimal import Decimal
from typing import Any

from app.properties.models import BusinessType, Property, PropertyStatus, PropertyType


def calculate_visibility_score(property_obj: Property) -> int:
    """
    Calculate visibility score (0-100) based on property completeness and appeal.

    Criteria (total 100 points):
    - Informações básicas (25): título, descrição, código, imagem
    - Localização (20): cidade, bairro, endereço, CEP
    - Características (25): área, quartos, banheiros, vagas, extras
    - Financeiro (20): preço (venda ou aluguel) vale 18 pts; condomínio/IPTU bônus opcional +2 pts
    - Comercial (10): status publicado, agente atribuído

    Args:
        property_obj: Property instance

    Returns:
        Score from 0 to 100
    """
    score = 0

    # --- Informações básicas (25 pts) ---
    if property_obj.title and len(property_obj.title.strip()) >= 5:
        score += 5
    if property_obj.description and len(property_obj.description.strip()) >= 100:
        score += 10
    elif property_obj.description and len(property_obj.description.strip()) >= 50:
        score += 5
    if property_obj.code and len(property_obj.code.strip()) > 0:
        score += 5
    if property_obj.main_image_url and property_obj.main_image_url.strip():
        score += 5

    # --- Localização (20 pts) ---
    if property_obj.city and property_obj.city.strip():
        score += 5
    if property_obj.neighborhood and property_obj.neighborhood.strip():
        score += 5
    street_ok = property_obj.street and property_obj.street.strip()
    number_ok = property_obj.number and str(property_obj.number).strip()
    if street_ok and number_ok:
        score += 5
    elif street_ok or number_ok:
        score += 3
    if property_obj.zip_code and len(str(property_obj.zip_code).replace("-", "")) >= 8:
        score += 5

    # --- Características (25 pts máx) ---
    char_score = 0
    if _to_float(property_obj.area_total) and _to_float(property_obj.area_total) > 0:
        char_score += 5
    elif _to_float(property_obj.area_built) and _to_float(property_obj.area_built) > 0:
        char_score += 3
    if (property_obj.bedrooms or 0) > 0:
        char_score += 5
    if (property_obj.bathrooms or 0) > 0:
        char_score += 5
    if property_obj.parking_spaces is not None:
        char_score += 5
    elif property_obj.property_type in (PropertyType.APARTMENT, PropertyType.HOUSE):
        char_score += 2
    if property_obj.has_elevator or property_obj.furnished:
        char_score += 5
    elif property_obj.floor is not None:
        char_score += 2
    score += min(char_score, 25)

    # --- Financeiro (20 pts máx) ---
    # Preço (venda ou aluguel) é o principal; condomínio/IPTU são bônus opcional (nem sempre informados)
    price_val = _to_float(property_obj.price) or _to_float(property_obj.rent_price)
    fin_score = 0
    if price_val and price_val > 0:
        fin_score += 18  # Ter preço já garante quase toda a pontuação financeira
    if _to_float(property_obj.condo_fee) is not None or _to_float(property_obj.iptu) is not None:
        fin_score += 2   # Bônus opcional; não penaliza quem não informa
    score += min(fin_score, 20)

    # --- Comercial (10 pts) ---
    if property_obj.status == PropertyStatus.PUBLISHED:
        score += 5
    if property_obj.assigned_agent_id:
        score += 5

    return min(100, max(0, score))


def _to_float(value: Any) -> float | None:
    """Convert Decimal, str or number to float, or None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ".").strip()) if value.strip() else None
        except (ValueError, AttributeError):
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
