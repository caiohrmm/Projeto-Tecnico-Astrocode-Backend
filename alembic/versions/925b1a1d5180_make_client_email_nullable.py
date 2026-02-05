"""make_client_email_nullable

Revision ID: 925b1a1d5180
Revises: d82cda047c3a
Create Date: 2026-02-05 18:11:21.754307

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '925b1a1d5180'
down_revision: Union[str, None] = 'd82cda047c3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make email column nullable
    op.alter_column('clients', 'email',
                    existing_type=sa.String(length=255),
                    nullable=True)


def downgrade() -> None:
    # Revert email column to not nullable
    # Note: This will fail if there are NULL values in the database
    op.alter_column('clients', 'email',
                    existing_type=sa.String(length=255),
                    nullable=False)

