"""create clients table

Revision ID: 3dd24f59a2f1
Revises: 081944327cfb
Create Date: 2026-02-03 09:53:53.862206

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3dd24f59a2f1'
down_revision: Union[str, None] = '081944327cfb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create clients table
    op.create_table(
        "clients",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "lead_source",
            sa.Enum("WHATSAPP", "SITE", "PHONE", name="leadsource", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(op.f("ix_clients_id"), "clients", ["id"], unique=False)
    op.create_index(op.f("ix_clients_name"), "clients", ["name"], unique=False)
    op.create_index(op.f("ix_clients_phone"), "clients", ["phone"], unique=False)
    op.create_index(op.f("ix_clients_email"), "clients", ["email"], unique=False)
    op.create_index(op.f("ix_clients_lead_source"), "clients", ["lead_source"], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f("ix_clients_lead_source"), table_name="clients")
    op.drop_index(op.f("ix_clients_email"), table_name="clients")
    op.drop_index(op.f("ix_clients_phone"), table_name="clients")
    op.drop_index(op.f("ix_clients_name"), table_name="clients")
    op.drop_index(op.f("ix_clients_id"), table_name="clients")
    # Drop table
    op.drop_table("clients")
    # Drop enum type
    op.execute("DROP TYPE IF EXISTS leadsource")

