"""Service for calculating client lead scores."""

from datetime import datetime

from app.clients.models import Client, ClientStatus, UrgencyLevel


class LeadScoreService:
    """Service for calculating lead scores based on client data."""

    @staticmethod
    def calculate_lead_score(client: Client) -> int:
        """
        Calculate lead score (0-100) based on client data.

        Scoring factors:
        - Funnel status (0-100 points): Higher status = higher score
        - Urgency level (0-30 points): Higher urgency = higher score
        - Interest data completeness (0-25 points): More data = higher score
        - Contact history (0-11 points): More contact data = higher score

        Args:
            client: Client instance to calculate score for

        Returns:
            Lead score from 0 to 100
        """
        score = 0

        # 1. Funnel Status (0-100 points) - Most important factor
        status_score = LeadScoreService._get_status_score(client.current_status)
        score += status_score

        # 2. Urgency Level (0-30 points)
        urgency_score = LeadScoreService._get_urgency_score(client.current_urgency_level)
        score += urgency_score

        # 3. Interest Data Completeness (0-25 points)
        interest_score = LeadScoreService._get_interest_data_score(client)
        score += interest_score

        # 4. Contact History (0-11 points)
        contact_score = LeadScoreService._get_contact_history_score(client)
        score += contact_score

        # Ensure score is between 0 and 100
        return min(100, max(0, score))

    @staticmethod
    def _get_status_score(status: ClientStatus | None) -> int:
        """
        Get score based on funnel status.

        Args:
            status: Current client status

        Returns:
            Score points (0-100)
        """
        if status is None:
            return 0

        status_scores = {
            ClientStatus.NEW_LEAD: 5,
            ClientStatus.CONTACTED: 10,
            ClientStatus.QUALIFIED: 25,
            ClientStatus.VISIT_SCHEDULED: 35,
            ClientStatus.VISITING: 45,
            ClientStatus.PROPOSAL_SENT: 60,
            ClientStatus.NEGOTIATING: 75,
            ClientStatus.WON: 100,
            ClientStatus.LOST: 0,
            ClientStatus.INACTIVE: 0,
        }

        return status_scores.get(status, 0)

    @staticmethod
    def _get_urgency_score(urgency: UrgencyLevel | None) -> int:
        """
        Get score based on urgency level.

        Args:
            urgency: Current urgency level

        Returns:
            Score points (0-30)
        """
        if urgency is None:
            return 0

        urgency_scores = {
            UrgencyLevel.LOW: 5,
            UrgencyLevel.MEDIUM: 10,
            UrgencyLevel.HIGH: 20,
            UrgencyLevel.IMMEDIATE: 30,
        }

        return urgency_scores.get(urgency, 0)

    @staticmethod
    def _get_interest_data_score(client: Client) -> int:
        """
        Get score based on interest data completeness.

        Args:
            client: Client instance

        Returns:
            Score points (0-25)
        """
        score = 0

        # Each interest field adds points
        if client.current_interest_type is not None:
            score += 5
        if client.current_property_type is not None:
            score += 5
        if client.current_budget_min is not None:
            score += 5
        if client.current_budget_max is not None:
            score += 5
        if client.current_city_interest is not None:
            score += 5

        return score

    @staticmethod
    def _get_contact_history_score(client: Client) -> int:
        """
        Get score based on contact history completeness.

        Args:
            client: Client instance

        Returns:
            Score points (0-11)
        """
        score = 0

        if client.first_contact_at is not None:
            score += 3
        if client.last_contact_at is not None:
            score += 3
        if client.summary_notes is not None and client.summary_notes.strip():
            score += 2

        return score

