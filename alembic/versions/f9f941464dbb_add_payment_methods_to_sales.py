"""add_payment_methods_to_sales

Revision ID: f9f941464dbb
Revises: a99a768ecc09
Create Date: 2026-02-14 00:14:33.271605

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f9f941464dbb'
down_revision: Union[str, None] = '357cfb238719'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add payment_methods column to sales table
    op.add_column(
        'sales',
        sa.Column(
            'payment_methods',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="List of payment methods with values. Format: [{'method': 'CASH', 'value': 100000.00, 'description': 'Entrada'}, ...]"
        )
    )


def downgrade() -> None:
    # Remove payment_methods column
    op.drop_column('sales', 'payment_methods')

