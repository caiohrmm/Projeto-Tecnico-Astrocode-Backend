"""Property repository for database operations."""

import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.properties.models import BusinessType, Property, PropertyStatus, PropertyType
from app.properties.schemas import PropertyCreate, PropertyUpdate
from app.properties.visibility_score_service import calculate_visibility_score


class PropertyRepository:
    """Repository for property database operations."""

    def __init__(self, db: Session) -> None:
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create(self, property_data: PropertyCreate) -> Property:
        """
        Create a new property.

        Args:
            property_data: Property creation data

        Returns:
            Created property instance
        """
        property_dict = property_data.model_dump(exclude_unset=False)

        # Set default status if not provided
        if "status" not in property_dict or property_dict["status"] is None:
            property_dict["status"] = PropertyStatus.DRAFT

        db_property = Property(**property_dict)
        self.db.add(db_property)
        self.db.commit()
        self.db.refresh(db_property)
        return db_property

    def get_by_id(self, property_id: uuid.UUID) -> Property | None:
        """
        Get property by ID.

        Args:
            property_id: Property UUID

        Returns:
            Property instance or None if not found
        """
        stmt = select(Property).where(Property.id == property_id)
        return self.db.scalar(stmt)

    def get_by_code(self, code: str) -> Property | None:
        """
        Get property by code.

        Args:
            code: Property code

        Returns:
            Property instance or None if not found
        """
        stmt = select(Property).where(Property.code == code)
        return self.db.scalar(stmt)

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        property_type: PropertyType | None = None,
        business_type: BusinessType | None = None,
        status: PropertyStatus | None = None,
        city: str | None = None,
        state: str | None = None,
    ) -> List[Property]:
        """
        Get all properties with optional filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            property_type: Optional filter by property type
            business_type: Optional filter by business type
            status: Optional filter by status
            city: Optional filter by city
            state: Optional filter by state

        Returns:
            List of property instances
        """
        stmt = select(Property)

        if property_type:
            stmt = stmt.where(Property.property_type == property_type)
        if business_type:
            stmt = stmt.where(Property.business_type == business_type)
        if status:
            stmt = stmt.where(Property.status == status)
        if city:
            stmt = stmt.where(Property.city.ilike(f"%{city}%"))
        if state:
            stmt = stmt.where(Property.state == state.upper())

        # Order by visibility_score DESC (higher first), NULLs last, then created_at DESC
        stmt = (
            stmt.order_by(
                Property.visibility_score.desc().nullslast(),
                Property.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def find_recommended_properties(
        self,
        interest_type: str | None = None,
        property_type: PropertyType | None = None,
        city: str | None = None,
        budget_min: float | None = None,
        budget_max: float | None = None,
        limit: int = 5,
    ) -> List[Property]:
        """
        Find recommended properties based on client preferences.

        Args:
            interest_type: BUY or RENT
            property_type: Type of property (HOUSE, APARTMENT, etc.)
            city: City preference
            budget_min: Minimum budget
            budget_max: Maximum budget
            limit: Maximum number of properties to return

        Returns:
            List of recommended property instances, ranked by relevance
        """
        from sqlalchemy import and_, or_, func

        import logging
        logger = logging.getLogger(__name__)
        
        stmt = select(Property)

        # Only show published properties
        stmt = stmt.where(Property.status == PropertyStatus.PUBLISHED)
        
        # Filter by business type based on interest
        if interest_type == "BUY":
            stmt = stmt.where(
                or_(
                    Property.business_type == BusinessType.SALE,
                    Property.business_type == BusinessType.BOTH,
                )
            )
        elif interest_type == "RENT":
            stmt = stmt.where(
                or_(
                    Property.business_type == BusinessType.RENT,
                    Property.business_type == BusinessType.BOTH,
                )
            )

        # Filter by property type
        if property_type:
            stmt = stmt.where(Property.property_type == property_type)

        # Filter by city (case-insensitive, flexible matching)
        if city:
            # Normalize city name for better matching
            city_normalized = city.strip().title()
            city_lower = city.strip().lower()
            # Use flexible matching: exact match or contains (for better results)
            # This helps find properties even with slight variations in city name
            # Also try without accents/diacritics for better matching
            import unicodedata
            city_no_accents = ''.join(
                c for c in unicodedata.normalize('NFD', city_lower)
                if unicodedata.category(c) != 'Mn'
            )
            
            stmt = stmt.where(
                or_(
                    func.lower(func.trim(Property.city)) == city_lower,  # Exact match (case-insensitive, trimmed)
                    Property.city.ilike(f"%{city_normalized}%"),  # Contains match (normalized)
                    Property.city.ilike(f"%{city_lower}%"),  # Contains match (lowercase)
                    func.lower(func.trim(Property.city)).like(f"%{city_no_accents}%"),  # Match without accents
                )
            )

        # Filter by budget (flexible: allow 20% tolerance for better matches)
        if budget_min is not None or budget_max is not None:
            price_conditions = []
            # Add tolerance: allow properties within 20% of budget range
            tolerance_min = budget_min * 0.8 if budget_min else None
            tolerance_max = budget_max * 1.2 if budget_max else None
            
            if interest_type == "BUY":
                # For buying, check price field
                if budget_min is not None:
                    # Allow properties up to 20% below min budget
                    price_conditions.append(Property.price >= tolerance_min)
                if budget_max is not None:
                    # Allow properties up to 20% above max budget
                    price_conditions.append(Property.price <= tolerance_max)
            elif interest_type == "RENT":
                # For renting, check rent_price field
                if budget_min is not None:
                    price_conditions.append(Property.rent_price >= tolerance_min)
                if budget_max is not None:
                    price_conditions.append(Property.rent_price <= tolerance_max)
            else:
                # If interest type not specified, check both
                if budget_min is not None:
                    price_conditions.append(
                        or_(
                            Property.price >= tolerance_min,
                            Property.rent_price >= tolerance_min,
                        )
                    )
                if budget_max is not None:
                    price_conditions.append(
                        or_(
                            Property.price <= tolerance_max,
                            Property.rent_price <= tolerance_max,
                        )
                    )

            if price_conditions:
                stmt = stmt.where(and_(*price_conditions))

        # Order by visibility_score (higher first), then created_at
        stmt = (
            stmt.order_by(
                Property.visibility_score.desc().nullslast(),
                Property.created_at.desc(),
            )
            .limit(limit)
        )
        
        final_properties = list(self.db.scalars(stmt).all())

        return final_properties

    def update(
        self,
        property: Property,
        property_data: PropertyUpdate,
    ) -> Property:
        """
        Update property information.

        Args:
            property: Property instance to update
            property_data: Update data (only provided fields will be updated)

        Returns:
            Updated property instance
        """
        update_data = property_data.model_dump(exclude_unset=True)

        # Update published_at if status changes to PUBLISHED
        if "status" in update_data and update_data["status"] == PropertyStatus.PUBLISHED:
            if property.published_at is None:
                from datetime import datetime

                update_data["published_at"] = datetime.utcnow()

        for field, value in update_data.items():
            setattr(property, field, value)

        self.db.commit()
        self.db.refresh(property)
        # Recalculate visibility score for consistent ordering
        property.visibility_score = calculate_visibility_score(property)
        self.db.commit()
        self.db.refresh(property)
        return property

    def update_main_image_url(
        self,
        property: Property,
        image_url: str,
    ) -> Property:
        """
        Update property main image URL.

        Args:
            property: Property instance to update
            image_url: New main image URL

        Returns:
            Updated property instance
        """
        property.main_image_url = image_url
        self.db.commit()
        self.db.refresh(property)
        return property

    def delete(self, property: Property) -> None:
        """
        Delete a property.

        Args:
            property: Property instance to delete
        """
        self.db.delete(property)
        self.db.commit()

