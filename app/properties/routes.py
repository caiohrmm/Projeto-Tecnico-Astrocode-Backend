"""Property routes for CRUD operations."""

import uuid
from typing import List

import os
import re
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, get_current_agent_or_manager
from app.config.settings import get_settings
from app.core.logging import get_logger
from app.db import get_db
from app.properties.models import BusinessType, Property, PropertyStatus, PropertyType
from app.properties.repository import PropertyRepository
from app.properties.schemas import AddressData, PropertyCreate, PropertyResponse, PropertyUpdate
from app.services.cloudinary_service import get_cloudinary_service
from app.users.models import User
from app.users.repository import UserRepository

router = APIRouter(prefix="/properties", tags=["properties"])
logger = get_logger(__name__)


def is_google_maps_url(input_str: str) -> bool:
    """
    Check if the input string is a Google Maps URL.
    
    Args:
        input_str: Input string to check
        
    Returns:
        True if the string is a Google Maps URL, False otherwise
    """
    if not input_str or not isinstance(input_str, str):
        return False
    
    input_lower = input_str.lower().strip()
    return (
        'maps.google.com' in input_lower or
        'maps.app.goo.gl' in input_lower or
        'goo.gl/maps' in input_lower or
        input_lower.startswith('https://maps.app.goo.gl/') or
        input_lower.startswith('http://maps.app.goo.gl/')
    )


async def resolve_short_url(url: str) -> str:
    """
    Resolve a short Google Maps URL to its final expanded URL.
    
    Args:
        url: Short URL to resolve (e.g., https://maps.app.goo.gl/xxxx)
        
    Returns:
        Final expanded URL after following redirects
        
    Raises:
        HTTPException: If the URL cannot be resolved
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.get(url, follow_redirects=True)
            return str(response.url)
    except Exception as e:
        logger.error(f"Failed to resolve short URL {url}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not resolve Google Maps short URL: {str(e)}",
        )


def is_valid_place_id(place_id: str) -> bool:
    """
    Validate if a string is a valid Google Place ID.
    
    Google Place IDs are:
    - Opaque strings (not human-readable)
    - Typically 27+ characters long
    - Contain alphanumeric characters, hyphens, and underscores
    - No spaces or special characters that indicate human-readable text
    
    Args:
        place_id: String to validate
        
    Returns:
        True if it appears to be a valid Place ID, False otherwise
    """
    if not place_id or not isinstance(place_id, str):
        return False
    
    place_id = place_id.strip()
    
    # Place IDs are typically long (Google uses 27+ character IDs)
    if len(place_id) < 20:
        return False
    
    # Place IDs should not contain spaces (human-readable text does)
    if ' ' in place_id:
        return False
    
    # Place IDs are opaque strings, not human-readable
    # They typically contain alphanumeric, hyphens, underscores
    # If it looks like readable text (contains common words), it's not a place_id
    if any(char.isalpha() and char.isupper() and char.islower() for char in place_id):
        # Mixed case might indicate readable text
        pass
    
    # Valid pattern: alphanumeric, hyphens, underscores, no spaces
    if not re.match(r'^[A-Za-z0-9_-]+$', place_id):
        return False
    
    return True


def extract_place_id_from_url(url: str) -> str | None:
    """
    Extract place_id from a Google Maps URL.
    
    Args:
        url: Google Maps URL
        
    Returns:
        Valid place_id if found and validated, None otherwise
    """
    # Try to find place_id in query parameters
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    
    if 'place_id' in query_params:
        place_id = query_params['place_id'][0]
        if is_valid_place_id(place_id):
            return place_id
        logger.warning(f"Invalid place_id extracted from URL query: {place_id[:50]}...")
    
    # Try to find in path (e.g., /maps/place/...)
    # Note: Path-based place IDs are less common, but we check anyway
    path_match = re.search(r'/place/([^/?]+)', parsed.path)
    if path_match:
        place_id = path_match.group(1)
        if is_valid_place_id(place_id):
            return place_id
        logger.warning(f"Invalid place_id extracted from URL path: {place_id[:50]}...")
    
    return None


def extract_coordinates_from_url(url: str) -> tuple[float, float] | None:
    """
    Extract latitude and longitude from a Google Maps URL.
    
    Supports formats like:
    - @lat,lng
    - @lat,lng,zoom
    - ?q=lat,lng
    
    Args:
        url: Google Maps URL
        
    Returns:
        Tuple of (latitude, longitude) if found, None otherwise
    """
    # Try @lat,lng pattern (most common)
    at_pattern = re.search(r'@(-?\d+\.?\d*),(-?\d+\.?\d*)', url)
    if at_pattern:
        try:
            lat = float(at_pattern.group(1))
            lng = float(at_pattern.group(2))
            return (lat, lng)
        except ValueError:
            pass
    
    # Try q=lat,lng pattern
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    if 'q' in query_params:
        q_value = query_params['q'][0]
        coords_match = re.search(r'(-?\d+\.?\d*),(-?\d+\.?\d*)', q_value)
        if coords_match:
            try:
                lat = float(coords_match.group(1))
                lng = float(coords_match.group(2))
                return (lat, lng)
            except ValueError:
                pass
    
    return None


async def geocode_google_maps_url(url: str, api_key: str) -> dict:
    """
    Geocode a Google Maps URL by extracting place_id or coordinates.
    
    Args:
        url: Google Maps URL (may be short or full)
        api_key: Google API key
        
    Returns:
        Geocoding API response data
        
    Raises:
        HTTPException: If the URL cannot be geocoded
    """
    # Resolve short URLs
    if 'maps.app.goo.gl' in url.lower() or 'goo.gl/maps' in url.lower():
        logger.info(f"Resolving short Google Maps URL: {url}")
        url = await resolve_short_url(url)
        logger.info(f"Resolved to: {url}")
    
    # Try to extract and validate place_id first (most reliable)
    place_id = extract_place_id_from_url(url)
    if place_id and is_valid_place_id(place_id):
        logger.info(f"Using valid place_id from URL: {place_id[:20]}...")
        async with httpx.AsyncClient(timeout=10.0) as client:
            params = {
                "place_id": place_id,
                "key": api_key,
                "language": "pt-BR",
            }
            response = await client.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params=params
            )
            response.raise_for_status()
            return response.json()
    
    # Try to extract coordinates (fallback)
    coords = extract_coordinates_from_url(url)
    if coords:
        lat, lng = coords
        logger.info(f"Using coordinates from URL: {lat}, {lng}")
        async with httpx.AsyncClient(timeout=10.0) as client:
            params = {
                "latlng": f"{lat},{lng}",
                "key": api_key,
                "language": "pt-BR",
            }
            response = await client.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params=params
            )
            response.raise_for_status()
            return response.json()
    
    # If we can't extract valid place_id or coordinates, return error
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "Could not extract valid location information from Google Maps URL. "
            "The URL must contain a valid place_id or coordinates (@lat,lng). "
            "Please use a direct link to a place or location on Google Maps, "
            "or use a plain text address instead."
        ),
    )


def _validate_agent_is_corretor(assigned_agent_id: uuid.UUID | None, db: Session) -> None:
    """
    Validate that assigned_agent_id belongs to a user with 'corretor' role.

    Args:
        assigned_agent_id: UUID of the agent to validate
        db: Database session

    Raises:
        HTTPException: If agent_id is provided but user doesn't have 'corretor' role
    """
    if assigned_agent_id is None:
        return  # No validation needed if no agent is assigned

    user_repo = UserRepository(db)
    agent = user_repo.get_by_id(assigned_agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {assigned_agent_id} not found",
        )

    # Check if user has 'corretor' role
    role_names = [role.name for role in agent.roles]
    if "corretor" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User {assigned_agent_id} does not have 'corretor' role. Only users with 'corretor' role can be assigned as agents.",
        )


@router.post(
    "/",
    response_model=PropertyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar imóvel",
    description="""
Cria um novo imóvel no portfólio.

**Regras:**
- **Código único:** `code` não pode repetir outro imóvel (400 se já existir).
- **Agente:** se `assigned_agent_id` for informado, o usuário deve ter role **corretor** (400 se não for; 404 se usuário não existir).
- **Status:** padrão DRAFT se não informado. O score de visibilidade é calculado automaticamente na criação.

Requer autenticação.
    """.strip(),
    responses={
        201: {"description": "Imóvel criado"},
        400: {"description": "Código já existe ou agent_id não é corretor"},
        401: {"description": "Não autenticado"},
        404: {"description": "Agente não encontrado"},
        422: {"description": "Dados inválidos"},
    },
)
def create_property(
    property_data: PropertyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PropertyResponse:
    # Validate assigned_agent_id if provided
    _validate_agent_is_corretor(property_data.assigned_agent_id, db)

    # Check if code already exists
    property_repo = PropertyRepository(db)
    existing_property = property_repo.get_by_code(property_data.code)
    if existing_property:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Property with code '{property_data.code}' already exists",
        )

    property = property_repo.create(property_data)
    return PropertyResponse.model_validate(property)


@router.get(
    "/",
    response_model=List[PropertyResponse],
    summary="Listar imóveis",
    description="""
Lista imóveis com paginação e filtros opcionais.

**Filtros:** property_type, business_type, status, city (correspondência parcial), state (2 letras).  
**available_only:** quando true, ignora o parâmetro status e retorna apenas imóveis PUBLISHED (exclui SOLD, RENTED, etc.).  
**Ordenação:** por visibility_score (maior primeiro), depois por created_at (mais recentes primeiro).

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Lista de imóveis"},
        401: {"description": "Não autenticado"},
    },
)
def list_properties(
    skip: int = Query(0, ge=0, description="Registros a pular (paginação)"),
    limit: int = Query(100, ge=1, le=1000, description="Máximo de registros a retornar"),
    property_type: PropertyType | None = Query(None, description="Filtrar por tipo de imóvel"),
    business_type: BusinessType | None = Query(None, description="Filtrar por tipo de negócio (SALE, RENT, BOTH)"),
    status: PropertyStatus | None = Query(None, description="Filtrar por status"),
    available_only: bool = Query(False, description="Se true, retorna apenas PUBLISHED"),
    city: str | None = Query(None, description="Filtrar por cidade (parcial)"),
    state: str | None = Query(None, description="Filtrar por estado (2 letras)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[PropertyResponse]:
    effective_status = PropertyStatus.PUBLISHED if available_only else status
    property_repo = PropertyRepository(db)
    properties = property_repo.get_all(
        skip=skip,
        limit=limit,
        property_type=property_type,
        business_type=business_type,
        status=effective_status,
        city=city,
        state=state,
    )
    return [PropertyResponse.model_validate(prop) for prop in properties]


@router.get(
    "/{property_id}",
    response_model=PropertyResponse,
    summary="Buscar imóvel por ID",
    description="Retorna um imóvel pelo UUID. Inclui dados de endereço, características, valores, status, agente e URL da imagem principal.",
    responses={
        200: {"description": "Imóvel encontrado"},
        401: {"description": "Não autenticado"},
        404: {"description": "Imóvel não encontrado"},
    },
)
def get_property(
    property_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PropertyResponse:
    property_repo = PropertyRepository(db)
    property = property_repo.get_by_id(property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with ID {property_id} not found",
        )

    return PropertyResponse.model_validate(property)


@router.put(
    "/{property_id}",
    response_model=PropertyResponse,
    summary="Atualizar imóvel",
    description="""
Atualização parcial: apenas os campos enviados são alterados.

**Regras:**
- **Código:** ao alterar, não pode coincidir com o de outro imóvel (400).
- **Agente:** se `assigned_agent_id` for informado, deve ser usuário com role corretor (400/404).

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Imóvel atualizado"},
        400: {"description": "Código já existe ou agent_id não é corretor"},
        401: {"description": "Não autenticado"},
        403: {"description": "Imóvel vendido ou alugado não pode ser editado"},
        404: {"description": "Imóvel ou agente não encontrado"},
        422: {"description": "Dados inválidos"},
    },
)
def update_property(
    property_id: uuid.UUID,
    property_data: PropertyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PropertyResponse:
    # Validate assigned_agent_id if provided
    _validate_agent_is_corretor(property_data.assigned_agent_id, db)

    property_repo = PropertyRepository(db)
    property = property_repo.get_by_id(property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with ID {property_id} not found",
        )

    # Imóvel vendido ou alugado não pode mais ser alterado (integridade com vendas registradas)
    if property.status in (PropertyStatus.SOLD, PropertyStatus.RENTED):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Imóvel vendido ou alugado não pode ser editado. O status está vinculado a uma venda/aluguel concluído.",
        )

    # Check if code is being updated and if it already exists
    if property_data.code is not None and property_data.code != property.code:
        existing_property = property_repo.get_by_code(property_data.code)
        if existing_property:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Property with code '{property_data.code}' already exists",
            )

    updated_property = property_repo.update(property, property_data)
    return PropertyResponse.model_validate(updated_property)


@router.delete(
    "/{property_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir imóvel",
    description="""
Remove o imóvel do sistema. Operação irreversível.

**Permissão:** apenas usuários com role **corretor** ou **gestor**. Atendentes não podem excluir.

Requer autenticação.
    """.strip(),
    responses={
        204: {"description": "Imóvel excluído"},
        401: {"description": "Não autenticado"},
        403: {"description": "Sem permissão (requer corretor ou gestor)"},
        404: {"description": "Imóvel não encontrado"},
    },
)
def delete_property(
    property_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_agent_or_manager),
) -> None:
    property_repo = PropertyRepository(db)
    property = property_repo.get_by_id(property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with ID {property_id} not found",
        )

    property_repo.delete(property)


@router.post(
    "/{property_id}/main-image",
    response_model=PropertyResponse,
    status_code=status.HTTP_200_OK,
    summary="Enviar imagem principal do imóvel",
    description="""
Envia a imagem principal do imóvel para o Cloudinary e atualiza `main_image_url` no imóvel.

**Armazenamento:** pasta `properties/{property_id}/main_image` no Cloudinary.  
**Formatos:** JPEG, PNG ou WebP (validação e tamanho máx. definidos no serviço Cloudinary).  
**Permissão:** qualquer usuário autenticado (atendente, corretor, gestor).

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Imóvel atualizado com nova URL da imagem"},
        401: {"description": "Não autenticado"},
        404: {"description": "Imóvel não encontrado"},
        500: {"description": "Falha no upload da imagem"},
    },
)
def upload_property_main_image(
    property_id: uuid.UUID,
    file: UploadFile = File(..., description="Arquivo da imagem (JPEG, PNG ou WebP)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PropertyResponse:
    # Get property
    property_repo = PropertyRepository(db)
    property = property_repo.get_by_id(property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with ID {property_id} not found",
        )

    # Get Cloudinary service
    cloudinary_service = get_cloudinary_service()

    # Upload image to Cloudinary
    try:
        image_url = cloudinary_service.upload_property_main_image(
            file=file,
            property_id=property_id,
        )
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors, etc.)
        raise
    except Exception as e:
        logger.error(f"Failed to upload image for property {property_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload image: {str(e)}",
        )

    # Update property with new image URL
    updated_property = property_repo.update_main_image_url(
        property=property,
        image_url=image_url,
    )

    logger.info(
        f"Successfully updated main image for property {property_id} "
        f"(user: {current_user.email})"
    )

    return PropertyResponse.model_validate(updated_property)


@router.get(
    "/geocode/address",
    response_model=AddressData,
    summary="Geocodificar endereço",
    description="""
Converte um endereço ou local em dados estruturados usando a API do Google (Geocoding).

**Entrada aceita:**
- Texto livre (ex.: "Rua Exemplo, 123, São Paulo, SP").
- URL do Google Maps (completa ou encurtada; place_id ou coordenadas @lat,lng são extraídos).

**Resposta:** endereço parseado (rua, número, bairro, cidade, estado, CEP, latitude, longitude).  
**Configuração:** requer `GOOGLE_API_KEY` no ambiente; sem chave retorna 503.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Endereço geocodificado (AddressData)"},
        400: {"description": "Endereço inválido ou sem place_id/coordenadas na URL"},
        401: {"description": "Não autenticado"},
        404: {"description": "Nenhum resultado para o endereço"},
        503: {"description": "Chave do Google não configurada ou API indisponível"},
    },
)
async def geocode_address(
    address: str = Query(..., description="Endereço, lugar ou URL do Google Maps para geocodificar"),
    current_user: User = Depends(get_current_active_user),
) -> AddressData:
    settings = get_settings()
    
    # Check if API key is configured
    # Pydantic Settings reads from environment variables, so GOOGLE_API_KEY should be available
    api_key_raw = getattr(settings, 'google_api_key', '') or os.getenv('GOOGLE_API_KEY', '')
    
    # Clean API key: remove whitespace, quotes, leading dashes/hyphens, newlines, carriage returns
    # Remove all whitespace first, then quotes, then leading dashes
    api_key = api_key_raw.strip()
    api_key = api_key.strip('"').strip("'")  # Remove quotes
    api_key = api_key.lstrip('-').lstrip('–').lstrip('—')  # Remove leading dashes (regular, en-dash, em-dash)
    api_key = api_key.replace('\n', '').replace('\r', '').replace(' ', '').replace('\t', '')  # Remove all whitespace
    
    if not api_key:
        logger.error("Google API key is not configured or is empty after cleaning")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google API key is not configured. Please set GOOGLE_API_KEY in .env file and restart the server",
        )
    
    # Log cleaned API key info (without exposing full key)
    if api_key_raw != api_key:
        logger.info(f"API key was cleaned (original length: {len(api_key_raw)}, cleaned length: {len(api_key)}, starts with: {api_key[:10]}...)")
    
    # Clean and validate input
    address = address.strip() if address else ""
    if not address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Address or location input is required",
        )
    
    # Log API key status (without exposing the key)
    logger.debug(f"Using Google API key (length: {len(api_key)}, starts with: {api_key[:10]}...)")
    
    try:
        # Check if input is a Google Maps URL
        if is_google_maps_url(address):
            logger.info(f"Detected Google Maps URL: {address}")
            # Ensure API key is clean before passing to geocode function
            data = await geocode_google_maps_url(address, api_key.strip())
        else:
            # Regular address geocoding - use "address" parameter for text input
            # NEVER use address text as place_id
            logger.info(f"Geocoding request for address text: {address[:100]}...")
            logger.debug(f"API key being used (first 15 chars): {api_key[:15]}... (total length: {len(api_key)})")
            
            # Validate that this is not being mistaken for a place_id
            if is_valid_place_id(address):
                logger.warning(
                    f"Input looks like a place_id but was provided as text. "
                    f"Using 'address' parameter instead of 'place_id' to avoid errors."
                )
            
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "address": address,  # Always use "address" for text input
                "key": api_key,
                "language": "pt-BR",
                "region": "br",  # Prioritize Brazil results
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
        logger.info(f"Geocoding API response status: {data.get('status')}")
        if data.get('error_message'):
            logger.error(f"Google API error message: {data.get('error_message')}")
        
        # Handle different Google API response statuses
        api_status = data.get("status", "UNKNOWN_ERROR")
        error_message_detail = data.get("error_message", "")
        
        if api_status != "OK":
            error_message = f"Geocoding failed: {api_status}"
            
            # Provide helpful error messages based on status
            if api_status == "REQUEST_DENIED":
                logger.error(f"Geocoding REQUEST_DENIED. Error message: {error_message_detail}")
                error_message = (
                    "Geocoding request denied by Google API. "
                    "Please verify in Google Cloud Console:\n"
                    "1. Geocoding API is ENABLED\n"
                    "2. Places API is ENABLED (optional but recommended)\n"
                    "3. API key is valid and not expired\n"
                    "4. API key restrictions (if any) allow requests from this server\n"
                    "5. Billing is enabled (Google requires billing for Maps APIs)\n\n"
                    f"Google error details: {error_message_detail if error_message_detail else 'No additional details'}",
                )
            elif api_status == "INVALID_REQUEST":
                error_message = f"Invalid geocoding request. Please check the address format. {error_message_detail}"
            elif api_status == "OVER_QUERY_LIMIT":
                error_message = "Geocoding API quota exceeded. Please try again later or check your billing."
            elif api_status == "ZERO_RESULTS":
                error_message = "No results found for this address. Please try a more specific address."
            
            logger.error(f"Geocoding failed with status {api_status}: {error_message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message,
            )
        
        if not data.get("results"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No results found for this address",
            )
        
        # Parse the first result
        result = data["results"][0]
        components = result.get("address_components", [])
        geometry = result.get("geometry", {}).get("location", {})
        
        # Extract address components
        address_data = AddressData()
        
        # Extract coordinates
        if geometry.get("lat") and geometry.get("lng"):
            address_data.latitude = str(geometry["lat"])
            address_data.longitude = str(geometry["lng"])
        
        # Parse address components
        street_parts = []
        number = None
        
        for component in components:
            types = component.get("types", [])
            long_name = component.get("long_name", "")
            short_name = component.get("short_name", "")
            
            if "street_number" in types:
                number = long_name
            elif "route" in types or "street_address" in types:
                street_parts.append(long_name)
            elif "sublocality_level_1" in types or "sublocality" in types or "neighborhood" in types:
                if not address_data.neighborhood:
                    address_data.neighborhood = long_name
            elif "administrative_area_level_2" in types or "locality" in types:
                if not address_data.city:
                    address_data.city = long_name
            elif "administrative_area_level_1" in types:
                if not address_data.state:
                    # Extract state abbreviation (2 letters)
                    address_data.state = short_name.upper()[:2]
            elif "postal_code" in types:
                if not address_data.zip_code:
                    # Remove non-numeric characters from postal code
                    address_data.zip_code = "".join(filter(str.isdigit, long_name))
        
        # Combine street parts
        if street_parts:
            address_data.street = " ".join(street_parts)
        
        # Set number if found
        if number:
            address_data.number = number
        else:
            # Try to extract number from formatted address
            formatted = result.get("formatted_address", "")
            # Simple extraction - look for number pattern
            import re
            number_match = re.search(r'\b(\d+)\b', formatted)
            if number_match:
                address_data.number = number_match.group(1)
        
        return address_data
        
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to connect to Google Geocoding API: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Geocoding error: {str(e)}",
        )

