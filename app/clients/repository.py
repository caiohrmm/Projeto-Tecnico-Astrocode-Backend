"""Client repository for database operations."""

import logging
import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.models import Client, LeadSource
from app.clients.schemas import ClientCreate, ClientUpdate

logger = logging.getLogger(__name__)


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
        
        NOTE: The system is ALWAYS ATTENTIVE to changes. When a client is created,
        it starts with default values. As soon as the first attendance is created:
        - AI analyzes the conversation
        - Detects interest, budget, urgency, property type
        - Automatically updates the client profile through State Derivation Service
        
        ⚠️ CRITICAL: Client profile reflects ONLY the current ACTIVE cycle:
        - Profile is derived ONLY from signals in the ACTIVE attendance cycle
        - When a new ACTIVE cycle starts, profile is updated based ONLY on that cycle
        - Previous cycles (COMPLETED, LOST, ABANDONED) are NOT considered
        - This ensures the profile always reflects the client's current objective and context
        
        The client profile is continuously updated by AI through attendances:
        - New attendance in ACTIVE cycle → AI detects changes → Updates profile
        - Attendance update in ACTIVE cycle → AI re-analyzes → Updates profile
        - All changes are detected automatically, no manual intervention needed

        Args:
            client_data: Client creation data (only name, phone, email, lead_source required)

        Returns:
            Created client instance
        """
        # Extract all fields from client_data, including optional ones
        # NOTE: Some fields exist apenas no schema (não são colunas da tabela)
        # e não podem ser passados para o modelo SQLAlchemy.
        client_dict = client_data.model_dump(
            exclude_unset=False,
            exclude={
                "use_ai_classification", # flag de controle da IA, não persiste
            },
        )
        
        # Set default status if not provided
        from app.clients.models import ClientStatus
        if "current_status" not in client_dict or client_dict["current_status"] is None:
            client_dict["current_status"] = ClientStatus.NEW_LEAD
        
        # AI-controlled fields (lead_score, interest_type, property_type, etc.) are set to defaults
        # and will be automatically updated by AI when the first attendance is created.
        # The system is always attentive - any new attendance triggers AI analysis
        # which updates the client profile through State Derivation Service.
        
        db_client = Client(**client_dict)
        self.db.add(db_client)
        self.db.flush()  # Flush to get the client ID
        
        # AI-controlled fields are updated automatically:
        # - When first attendance is created → AI analyzes → Updates profile
        # - When attendance is updated → AI re-analyzes → Updates profile
        # - All changes are detected and applied incrementally
        
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
        search: str | None = None,
    ) -> List[Client]:
        """
        Get all clients with optional filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            lead_source: Optional filter by lead source
            search: Optional search query to filter by name or phone

        Returns:
            List of client instances
        """
        from sqlalchemy import or_
        
        stmt = select(Client)
        
        # Search filter (name or phone)
        if search:
            search_term = f"%{search.strip()}%"
            # Remove non-digit characters from search for phone matching
            phone_digits = ''.join(filter(str.isdigit, search.strip()))
            if phone_digits:
                # Search in name (case-insensitive) or phone (exact digits match)
                stmt = stmt.where(
                    or_(
                        Client.name.ilike(search_term),
                        Client.phone.like(f"%{phone_digits}%")
                    )
                )
            else:
                # Only search in name if no digits found
                stmt = stmt.where(Client.name.ilike(search_term))
        
        # Lead source filter
        if lead_source:
            stmt = stmt.where(Client.lead_source == lead_source)
        
        stmt = stmt.offset(skip).limit(limit).order_by(Client.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def update(
        self,
        client: Client,
        client_data: ClientUpdate,
        allow_ai_lead_score_update: bool = False,
        allow_ai_updates: bool = False,
    ) -> Client:
        """
        Update client information.

        Args:
            client: Client instance to update
            client_data: Update data (only provided fields will be updated)
            allow_ai_lead_score_update: If True, allow lead_score updates (for AI-driven updates from state derivation)
            allow_ai_updates: If True, allow updates to AI-controlled fields (for AI-driven updates from state derivation)

        Returns:
            Updated client instance
        """
        update_data = client_data.model_dump(exclude_unset=True)
        
        # Fields controlled exclusively by AI - block manual updates unless allow_ai_updates=True
        ai_controlled_fields = [
            "current_lead_score",
            "current_interest_type",
            "current_property_type",
            "current_city_interest",
            "current_budget_min",
            "current_budget_max",
            "current_urgency_level",
        ]
        
        # Remove AI-controlled fields if provided manually (unless explicitly allowed)
        for field in ai_controlled_fields:
            if field in update_data:
                if field == "current_lead_score":
                    # Special handling for lead_score (backward compatibility)
                    if not allow_ai_lead_score_update:
                        update_data.pop("current_lead_score")
                        logger.info(f"Blocked manual update to current_lead_score for client {client.id} (AI-controlled field)")
                elif not allow_ai_updates:
                    # Block manual updates to other AI-controlled fields
                    update_data.pop(field)
                    logger.info(f"Blocked manual update to {field} for client {client.id} (AI-controlled field)")
        
        for field, value in update_data.items():
            setattr(client, field, value)
        
        # AI-controlled fields are updated exclusively by:
        # 1. State derivation from AISummary signals (automatic updates from attendances)
        # 2. Manual updates are blocked to maintain data integrity and AI consistency
        # 
        # The system is ALWAYS ATTENTIVE:
        # - New attendance → AI analyzes → Updates client profile automatically
        # - Attendance update → AI re-analyzes → Updates client profile automatically
        # - All changes in interest, budget, urgency, lead_score are detected and applied
        
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


