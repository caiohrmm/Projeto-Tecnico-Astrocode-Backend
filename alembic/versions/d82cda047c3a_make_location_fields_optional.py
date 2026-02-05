"""make_location_fields_optional

Revision ID: d82cda047c3a
Revises: 8b2285420a18
Create Date: 2026-02-05 00:08:32.810708

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd82cda047c3a'
down_revision: Union[str, None] = '8b2285420a18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make location fields optional (nullable)
    op.alter_column('properties', 'street',
                    existing_type=sa.String(length=255),
                    nullable=True)
    op.alter_column('properties', 'number',
                    existing_type=sa.String(length=20),
                    nullable=True)
    op.alter_column('properties', 'neighborhood',
                    existing_type=sa.String(length=255),
                    nullable=True)
    op.alter_column('properties', 'city',
                    existing_type=sa.String(length=255),
                    nullable=True)
    op.alter_column('properties', 'state',
                    existing_type=sa.String(length=2),
                    nullable=True)
    op.alter_column('properties', 'zip_code',
                    existing_type=sa.String(length=10),
                    nullable=True)


def downgrade() -> None:
    # Revert location fields to required (nullable=False)
    # Note: This will fail if there are NULL values in the database
    op.alter_column('properties', 'zip_code',
                    existing_type=sa.String(length=10),
                    nullable=False)
    op.alter_column('properties', 'state',
                    existing_type=sa.String(length=2),
                    nullable=False)
    op.alter_column('properties', 'city',
                    existing_type=sa.String(length=255),
                    nullable=False)
    op.alter_column('properties', 'neighborhood',
                    existing_type=sa.String(length=255),
                    nullable=False)
    op.alter_column('properties', 'number',
                    existing_type=sa.String(length=20),
                    nullable=False)
    op.alter_column('properties', 'street',
                    existing_type=sa.String(length=255),
                    nullable=False)

