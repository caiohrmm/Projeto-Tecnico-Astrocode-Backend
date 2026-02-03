"""Client repository for database operations."""

import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.models import Client, LeadSource
from app.clients.schemas import ClientCreate, ClientUpdate


class ClientRepository:
    """Repository for client database operations."""

    def __init__(self, db: Session) -> None:
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create(self, client_data: ClientCreate) -> Client:
        """
        Create a new client.

        Args:
            client_data: Client creation data

        Returns:
            Created client instance
        """
        db_client = Client(
            name=client_data.name,
            phone=client_data.phone,
            email=client_data.email,
            lead_source=client_data.lead_source,
        )
        self.db.add(db_client)
        self.db.commit()
        self.db.refresh(db_client)
        return db_client

    def get_by_id(self, client_id: uuid.UUID) -> Client | None:
        """
        Get client by ID.

        Args:
            client_id: Client UUID

        Returns:
            Client instance or None if not found
        """
        stmt = select(Client).where(Client.id == client_id)
        return self.db.scalar(stmt)

    def get_by_email(self, email: str) -> Client | None:
        """
        Get client by email.

        Args:
            email: Client email address

        Returns:
            Client instance or None if not found
        """
        stmt = select(Client).where(Client.email == email)
        return self.db.scalar(stmt)

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        lead_source: LeadSource | None = None,
    ) -> List[Client]:
        """
        Get all clients with optional filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            lead_source: Optional filter by lead source

        Returns:
            List of client instances
        """
        stmt = select(Client)
        if lead_source:
            stmt = stmt.where(Client.lead_source == lead_source)
        stmt = stmt.offset(skip).limit(limit).order_by(Client.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def update(
        self,
        client: Client,
        client_data: ClientUpdate,
    ) -> Client:
        """
        Update client information.

        Args:
            client: Client instance to update
            client_data: Update data (only provided fields will be updated)

        Returns:
            Updated client instance
        """
        update_data = client_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(client, field, value)
        self.db.commit()
        self.db.refresh(client)
        return client

    def delete(self, client: Client) -> None:
        """
        Delete a client.

        Args:
            client: Client instance to delete
        """
        self.db.delete(client)
        self.db.commit()

