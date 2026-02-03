"""Add auth_providers table for OAuth

Revision ID: 081944327cfb
Revises: 528ad3c713a1
Create Date: 2026-02-03 09:14:01.375437

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '081944327cfb'
down_revision: Union[str, None] = '528ad3c713a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create auth_providers table
    op.create_table(
        "auth_providers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        sa.Column("provider_email", sa.String(length=255), nullable=True),
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

    # Create indexes
    op.create_index(op.f("ix_auth_providers_id"), "auth_providers", ["id"], unique=False)
    op.create_index(
        op.f("ix_auth_providers_user_id"), "auth_providers", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_auth_providers_provider"), "auth_providers", ["provider"], unique=False
    )

    # Create foreign key
    op.create_foreign_key(
        "fk_auth_providers_user_id",
        "auth_providers",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Create unique constraint for provider + provider_user_id
    op.create_unique_constraint(
        "uq_provider_user_id",
        "auth_providers",
        ["provider", "provider_user_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_provider_user_id", "auth_providers", type_="unique")
    op.drop_constraint(
        "fk_auth_providers_user_id", "auth_providers", type_="foreignkey"
    )
    op.drop_index(op.f("ix_auth_providers_provider"), table_name="auth_providers")
    op.drop_index(op.f("ix_auth_providers_user_id"), table_name="auth_providers")
    op.drop_index(op.f("ix_auth_providers_id"), table_name="auth_providers")
    op.drop_table("auth_providers")

