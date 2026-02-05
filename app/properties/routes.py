"""Property routes for CRUD operations."""

import uuid
from typing import List

import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, get_current_agent_or_manager
from app.config.settings import get_settings
from app.core.logging import get_logger
from app.db import get_db
from app.properties.models import BusinessType, Property, PropertyStatus, PropertyType
from app.properties.repository import PropertyRepository
from app.properties.schemas import AddressData, PropertyCreate, PropertyResponse, PropertyUpdate
from app.users.models import User
from app.users.repository import UserRepository

router = APIRouter(prefix="/properties", tags=["properties"])
logger = get_logger(__name__)


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


@router.get("/geocode/address", response_model=AddressData)
def geocode_address(
    address: str = Query(..., description="Address or place to geocode"),
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
    api_key = getattr(settings, 'google_api_key', '') or os.getenv('GOOGLE_API_KEY', '')
    
    if not api_key or not api_key.strip():
        logger.error("Google API key is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google API key is not configured. Please set GOOGLE_API_KEY in .env file and restart the server",
        )
    
    # Log API key status (without exposing the key)
    logger.debug(f"Using Google API key (length: {len(api_key)}, starts with: {api_key[:10]}...)")
    
    try:
        # Call Google Geocoding API
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": address,
            "key": api_key,
            "language": "pt-BR",
            "region": "br",  # Prioritize Brazil results
        }
        
        logger.debug(f"Geocoding request for address: {address}")
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
        logger.debug(f"Geocoding API response status: {data.get('status')}")
        
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

