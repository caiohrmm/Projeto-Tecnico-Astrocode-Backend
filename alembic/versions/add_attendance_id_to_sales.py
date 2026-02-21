"""add attendance_id to sales

Revision ID: add_attendance_id_sales
Revises: a7b8c9d0e1f2
Create Date: 2026-02-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "add_attendance_id_sales"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sales",
        sa.Column(
            "attendance_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Atendimento que foi encerrado com esta venda (para sincronizar em cancelamento)",
        ),
    )
    op.create_foreign_key(
        "fk_sales_attendance_id",
        "sales",
        "attendances",
        ["attendance_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_sales_attendance_id", "sales", ["attendance_id"], unique=False)


def downgrade() -> None:
    op.drop_constraint("fk_sales_attendance_id", "sales", type_="foreignkey")
    op.drop_index("ix_sales_attendance_id", table_name="sales")
    op.drop_column("sales", "attendance_id")
