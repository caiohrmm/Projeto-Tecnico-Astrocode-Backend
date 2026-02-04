"""Visit repository for database operations."""

import uuid
from datetime import datetime
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.visits.models import Visit, VisitStatus
from app.visits.schemas import VisitCreate, VisitUpdate


class VisitRepository:
    """Repository for visit database operations."""

    def __init__(self, db: Session) -> None:
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create(self, visit_data: VisitCreate) -> Visit:
        """
        Create a new visit.

        Args:
            visit_data: Visit creation data

        Returns:
            Created visit instance
        """
        visit_dict = visit_data.model_dump(exclude_unset=False)

        # Set default status if not provided
        if "status" not in visit_dict or visit_dict["status"] is None:
            visit_dict["status"] = VisitStatus.SCHEDULED

        db_visit = Visit(**visit_dict)
        self.db.add(db_visit)
        self.db.commit()
        self.db.refresh(db_visit)
        return db_visit

    def get_by_id(self, visit_id: uuid.UUID) -> Visit | None:
        """
        Get visit by ID.

        Args:
            visit_id: Visit UUID

        Returns:
            Visit instance or None if not found
        """
        stmt = select(Visit).where(Visit.id == visit_id)
        return self.db.scalar(stmt)

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        client_id: uuid.UUID | None = None,
        broker_id: uuid.UUID | None = None,
        property_id: uuid.UUID | None = None,
        status: VisitStatus | None = None,
        scheduled_from: datetime | None = None,
        scheduled_to: datetime | None = None,
    ) -> List[Visit]:
        """
        Get all visits with optional filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            client_id: Optional filter by client ID
            broker_id: Optional filter by broker ID
            property_id: Optional filter by property ID
            status: Optional filter by status
            scheduled_from: Optional filter by scheduled date (from)
            scheduled_to: Optional filter by scheduled date (to)

        Returns:
            List of visit instances
        """
        stmt = select(Visit)

        if client_id:
            stmt = stmt.where(Visit.client_id == client_id)
        if broker_id:
            stmt = stmt.where(Visit.broker_id == broker_id)
        if property_id:
            stmt = stmt.where(Visit.property_id == property_id)
        if status:
            stmt = stmt.where(Visit.status == status)
        if scheduled_from:
            stmt = stmt.where(Visit.scheduled_at >= scheduled_from)
        if scheduled_to:
            stmt = stmt.where(Visit.scheduled_at <= scheduled_to)

        stmt = stmt.offset(skip).limit(limit).order_by(Visit.scheduled_at.asc())
        return list(self.db.scalars(stmt).all())

    def update(
        self,
        visit: Visit,
        visit_data: VisitUpdate,
    ) -> Visit:
        """
        Update visit information.

        Args:
            visit: Visit instance to update
            visit_data: Update data (only provided fields will be updated)

        Returns:
            Updated visit instance
        """
        update_data = visit_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(visit, field, value)

        self.db.commit()
        self.db.refresh(visit)
        return visit

    def delete(self, visit: Visit) -> None:
        """
        Delete a visit.

        Args:
            visit: Visit instance to delete
        """
        self.db.delete(visit)
        self.db.commit()

