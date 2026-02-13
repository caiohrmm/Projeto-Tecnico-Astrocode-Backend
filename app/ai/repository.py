"""AI Summary repository for database operations."""

import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.models import AISummary, AISummaryStatus
from app.ai.schemas import AISummaryCreate, AISummaryUpdate


class AISummaryRepository:
    """Repository for AI summary database operations."""

    def __init__(self, db: Session) -> None:
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create(self, summary_data: AISummaryCreate) -> AISummary:
        """
        Create a new AI summary.

        Args:
            summary_data: AI summary creation data

        Returns:
            Created AI summary instance
        """
        summary_dict = summary_data.model_dump(exclude_unset=False)

        # Set default status if not provided
        if "status" not in summary_dict or summary_dict["status"] is None:
            summary_dict["status"] = AISummaryStatus.PENDING

        # Convert recommended_properties UUIDs to strings for JSONB serialization
        if "recommended_properties" in summary_dict and summary_dict["recommended_properties"]:
            summary_dict["recommended_properties"] = [
                str(prop_id) if isinstance(prop_id, uuid.UUID) else prop_id
                for prop_id in summary_dict["recommended_properties"]
            ]

        db_summary = AISummary(**summary_dict)
        self.db.add(db_summary)
        self.db.commit()
        self.db.refresh(db_summary)
        return db_summary

    def get_by_id(self, summary_id: uuid.UUID) -> AISummary | None:
        """
        Get AI summary by ID.

        Args:
            summary_id: AI summary UUID

        Returns:
            AI summary instance or None if not found
        """
        stmt = select(AISummary).where(AISummary.id == summary_id)
        return self.db.scalar(stmt)

    def get_by_attendance_id(self, attendance_id: uuid.UUID) -> AISummary | None:
        """
        Get AI summary by attendance ID.

        Args:
            attendance_id: Attendance UUID

        Returns:
            AI summary instance or None if not found
        """
        stmt = select(AISummary).where(AISummary.attendance_id == attendance_id)
        return self.db.scalar(stmt)

    def get_by_client_id(
        self,
        client_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AISummary]:
        """
        Get all AI summaries for a client.

        Args:
            client_id: Client UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of AI summary instances
        """
        stmt = (
            select(AISummary)
            .where(AISummary.client_id == client_id)
            .offset(skip)
            .limit(limit)
            .order_by(AISummary.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        client_id: uuid.UUID | None = None,
        status: AISummaryStatus | None = None,
    ) -> List[AISummary]:
        """
        Get all AI summaries with optional filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            client_id: Optional filter by client ID
            status: Optional filter by status

        Returns:
            List of AI summary instances
        """
        stmt = select(AISummary)

        if client_id:
            stmt = stmt.where(AISummary.client_id == client_id)
        if status:
            stmt = stmt.where(AISummary.status == status)

        stmt = stmt.offset(skip).limit(limit).order_by(AISummary.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def update(
        self,
        summary: AISummary,
        summary_data: AISummaryUpdate,
    ) -> AISummary:
        """
        Update AI summary information.

        Args:
            summary: AI summary instance to update
            summary_data: Update data (only provided fields will be updated)

        Returns:
            Updated AI summary instance
        """
        update_data = summary_data.model_dump(exclude_unset=True)

        # Convert recommended_properties UUIDs to strings for JSONB serialization
        if "recommended_properties" in update_data and update_data["recommended_properties"]:
            update_data["recommended_properties"] = [
                str(prop_id) if isinstance(prop_id, uuid.UUID) else prop_id
                for prop_id in update_data["recommended_properties"]
            ]

        for field, value in update_data.items():
            setattr(summary, field, value)

        self.db.commit()
        self.db.refresh(summary)
        return summary

    def delete(self, summary: AISummary) -> None:
        """
        Delete an AI summary.

        Args:
            summary: AI summary instance to delete
        """
        self.db.delete(summary)
        self.db.commit()


