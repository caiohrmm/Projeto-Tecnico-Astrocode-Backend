"""Property repository for database operations."""

import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.properties.models import BusinessType, Property, PropertyStatus, PropertyType
from app.properties.schemas import PropertyCreate, PropertyUpdate


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

        stmt = stmt.offset(skip).limit(limit).order_by(Property.created_at.desc())
        return list(self.db.scalars(stmt).all())

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

