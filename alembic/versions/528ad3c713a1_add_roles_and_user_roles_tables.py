"""Add roles and user_roles tables

Revision ID: 528ad3c713a1
Revises: 26754306eee8
Create Date: 2026-02-03 00:00:07.380134

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '528ad3c713a1'
down_revision: Union[str, None] = '26754306eee8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create roles table
    op.create_table(
        "roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
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
    op.create_index(op.f("ix_roles_id"), "roles", ["id"], unique=False)
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)

    # Create user_roles association table
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
    )
    op.create_primary_key("pk_user_roles", "user_roles", ["user_id", "role_id"])
    op.create_foreign_key(
        "fk_user_roles_user_id",
        "user_roles",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_user_roles_role_id",
        "user_roles",
        "roles",
        ["role_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_user_roles_user_id"), "user_roles", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_roles_role_id"), "user_roles", ["role_id"], unique=False)

    # Seed default roles
    import uuid

    roles_table = sa.table(
        "roles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    default_roles = [
        {
            "id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
            "name": "atendente",
            "description": "Atendente responsável pelo atendimento inicial de clientes",
        },
        {
            "id": uuid.UUID("00000000-0000-0000-0000-000000000002"),
            "name": "corretor",
            "description": "Corretor responsável pela venda e negociação de imóveis",
        },
        {
            "id": uuid.UUID("00000000-0000-0000-0000-000000000003"),
            "name": "gestor",
            "description": "Gestor com acesso completo ao sistema e relatórios",
        },
    ]

    op.bulk_insert(roles_table, default_roles)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_roles_role_id"), table_name="user_roles")
    op.drop_index(op.f("ix_user_roles_user_id"), table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index(op.f("ix_roles_name"), table_name="roles")
    op.drop_index(op.f("ix_roles_id"), table_name="roles")
    op.drop_table("roles")

