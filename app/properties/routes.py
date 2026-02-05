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


@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
def create_property(
    property_data: PropertyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PropertyResponse:
    """
    Create a new property.

    Args:
        property_data: Property creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created property response
    """
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


@router.get("/", response_model=List[PropertyResponse])
def list_properties(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    property_type: PropertyType | None = Query(None, description="Filter by property type"),
    business_type: BusinessType | None = Query(None, description="Filter by business type"),
    status: PropertyStatus | None = Query(None, description="Filter by status"),
    city: str | None = Query(None, description="Filter by city (partial match)"),
    state: str | None = Query(None, description="Filter by state (2 letters)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[PropertyResponse]:
    """
    List all properties with optional filtering and pagination.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        property_type: Optional filter by property type
        business_type: Optional filter by business type
        status: Optional filter by status
        city: Optional filter by city
        state: Optional filter by state
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of property responses
    """
    property_repo = PropertyRepository(db)
    properties = property_repo.get_all(
        skip=skip,
        limit=limit,
        property_type=property_type,
        business_type=business_type,
        status=status,
        city=city,
        state=state,
    )
    return [PropertyResponse.model_validate(prop) for prop in properties]


@router.get("/{property_id}", response_model=PropertyResponse)
def get_property(
    property_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PropertyResponse:
    """
    Get a property by ID.

    Args:
        property_id: Property UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Property response

    Raises:
        HTTPException: If property is not found
    """
    property_repo = PropertyRepository(db)
    property = property_repo.get_by_id(property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with ID {property_id} not found",
        )

    return PropertyResponse.model_validate(property)


@router.put("/{property_id}", response_model=PropertyResponse)
def update_property(
    property_id: uuid.UUID,
    property_data: PropertyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PropertyResponse:
    """
    Update a property.

    Args:
        property_id: Property UUID
        property_data: Property update data (only provided fields will be updated)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated property response

    Raises:
        HTTPException: If property is not found
    """
    # Validate assigned_agent_id if provided
    _validate_agent_is_corretor(property_data.assigned_agent_id, db)

    property_repo = PropertyRepository(db)
    property = property_repo.get_by_id(property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with ID {property_id} not found",
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


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(
    property_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_agent_or_manager),
) -> None:
    """
    Delete a property.

    Only users with 'corretor' or 'gestor' roles can delete properties.
    Attendees (atendente) cannot delete properties.

    Args:
        property_id: Property UUID
        db: Database session
        current_user: Current authenticated user (must be corretor or gestor)

    Raises:
        HTTPException: If property is not found or user doesn't have permission
    """
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
)
def upload_property_main_image(
    property_id: uuid.UUID,
    file: UploadFile = File(..., description="Property main image file (JPEG, PNG, or WebP)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_agent_or_manager),
) -> PropertyResponse:
    """
    Upload main image for a property.

    The image is uploaded to Cloudinary and stored in the folder:
    properties/{property_id}/main_image

    Only users with 'corretor' or 'gestor' roles can upload images.

    Args:
        property_id: UUID of the property
        file: Image file to upload (JPEG, PNG, or WebP, max 10MB)
        db: Database session
        current_user: Current authenticated user (must be corretor or gestor)

    Returns:
        Updated property response with new main_image_url

    Raises:
        HTTPException: If property not found, file invalid, or upload fails
    """
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


@router.get("/geocode/address", response_model=AddressData)
async def geocode_address(
    address: str = Query(..., description="Address, place, or Google Maps URL to geocode"),
    current_user: User = Depends(get_current_active_user),
) -> AddressData:
    """
    Geocode an address using Google Geocoding API.
    
    Returns structured address data including street, number, neighborhood,
    city, state, zip_code, latitude, and longitude.
    
    Args:
        address: Address string to geocode (e.g., "Rua Exemplo, 123, São Paulo, SP")
        current_user: Current authenticated user
        
    Returns:
        AddressData with parsed address components
        
    Raises:
        HTTPException: If geocoding fails or API key is not configured
    """
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

