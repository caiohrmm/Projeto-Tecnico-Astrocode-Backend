"""add advanced client fields for funnel tracking and lead management

Revision ID: c6a06847cfc0
Revises: 3dd24f59a2f1
Create Date: 2026-02-03 16:21:14.245900

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c6a06847cfc0'
down_revision: Union[str, None] = '3dd24f59a2f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add funnel status and scoring fields
    op.add_column(
        "clients",
        sa.Column(
            "current_status",
            sa.Enum(
                "NEW_LEAD",
                "CONTACTED",
                "QUALIFIED",
                "VISIT_SCHEDULED",
                "VISITING",
                "PROPOSAL_SENT",
                "NEGOTIATING",
                "WON",
                "LOST",
                "INACTIVE",
                name="clientstatus",
                native_enum=False,
                length=20,
            ),
            nullable=True,
        ),
    )
    op.add_column("clients", sa.Column("current_lead_score", sa.Integer(), nullable=True))
    op.add_column(
        "clients",
        sa.Column(
            "current_urgency_level",
            sa.Enum("LOW", "MEDIUM", "HIGH", "IMMEDIATE", name="urgencylevel", native_enum=False, length=20),
            nullable=True,
        ),
    )

    # Add commercial assignment field
    op.add_column(
        "clients",
        sa.Column("assigned_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Add client interest fields
    op.add_column(
        "clients",
        sa.Column(
            "current_interest_type",
            sa.Enum("BUY", "RENT", "SELL", "INVEST", name="interesttype", native_enum=False, length=20),
            nullable=True,
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "current_property_type",
            sa.Enum("HOUSE", "APARTMENT", "LAND", "COMMERCIAL", "RURAL", name="propertytype", native_enum=False, length=20),
            nullable=True,
        ),
    )
    op.add_column(
        "clients",
        sa.Column("current_budget_min", sa.Numeric(precision=15, scale=2), nullable=True),
    )
    op.add_column(
        "clients",
        sa.Column("current_budget_max", sa.Numeric(precision=15, scale=2), nullable=True),
    )
    op.add_column("clients", sa.Column("current_city_interest", sa.String(length=255), nullable=True))

    # Add relationship management fields
    op.add_column("clients", sa.Column("first_contact_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("summary_notes", sa.Text(), nullable=True))

    # Create indexes for performance
    op.create_index(op.f("ix_clients_current_status"), "clients", ["current_status"], unique=False)
    op.create_index(op.f("ix_clients_current_lead_score"), "clients", ["current_lead_score"], unique=False)
    op.create_index(op.f("ix_clients_current_urgency_level"), "clients", ["current_urgency_level"], unique=False)
    op.create_index(op.f("ix_clients_assigned_agent_id"), "clients", ["assigned_agent_id"], unique=False)
    op.create_index(op.f("ix_clients_current_interest_type"), "clients", ["current_interest_type"], unique=False)
    op.create_index(op.f("ix_clients_current_property_type"), "clients", ["current_property_type"], unique=False)
    op.create_index(op.f("ix_clients_current_city_interest"), "clients", ["current_city_interest"], unique=False)
    op.create_index(op.f("ix_clients_first_contact_at"), "clients", ["first_contact_at"], unique=False)
    op.create_index(op.f("ix_clients_last_contact_at"), "clients", ["last_contact_at"], unique=False)
    op.create_index(op.f("ix_clients_next_follow_up_at"), "clients", ["next_follow_up_at"], unique=False)

    # Create foreign key for assigned_agent_id
    op.create_foreign_key(
        "fk_clients_assigned_agent_id",
        "clients",
        "users",
        ["assigned_agent_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop foreign key
    op.drop_constraint("fk_clients_assigned_agent_id", "clients", type_="foreignkey")

    # Drop indexes
    op.drop_index(op.f("ix_clients_next_follow_up_at"), table_name="clients")
    op.drop_index(op.f("ix_clients_last_contact_at"), table_name="clients")
    op.drop_index(op.f("ix_clients_first_contact_at"), table_name="clients")
    op.drop_index(op.f("ix_clients_current_urgency_level"), table_name="clients")
    op.drop_index(op.f("ix_clients_current_status"), table_name="clients")
    op.drop_index(op.f("ix_clients_current_property_type"), table_name="clients")
    op.drop_index(op.f("ix_clients_current_lead_score"), table_name="clients")
    op.drop_index(op.f("ix_clients_current_interest_type"), table_name="clients")
    op.drop_index(op.f("ix_clients_current_city_interest"), table_name="clients")
    op.drop_index(op.f("ix_clients_assigned_agent_id"), table_name="clients")

    # Drop columns
    op.drop_column("clients", "summary_notes")
    op.drop_column("clients", "next_follow_up_at")
    op.drop_column("clients", "last_contact_at")
    op.drop_column("clients", "first_contact_at")
    op.drop_column("clients", "current_city_interest")
    op.drop_column("clients", "current_budget_max")
    op.drop_column("clients", "current_budget_min")
    op.drop_column("clients", "current_property_type")
    op.drop_column("clients", "current_interest_type")
    op.drop_column("clients", "assigned_agent_id")
    op.drop_column("clients", "current_urgency_level")
    op.drop_column("clients", "current_lead_score")
    op.drop_column("clients", "current_status")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS clientstatus")
    op.execute("DROP TYPE IF EXISTS urgencylevel")
    op.execute("DROP TYPE IF EXISTS interesttype")
    op.execute("DROP TYPE IF EXISTS propertytype")

