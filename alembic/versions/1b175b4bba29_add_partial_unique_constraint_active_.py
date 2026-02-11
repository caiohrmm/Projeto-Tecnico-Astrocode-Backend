"""add_partial_unique_constraint_active_attendance_per_client

Revision ID: 1b175b4bba29
Revises: ec49bde7137a
Create Date: 2026-02-11 03:03:42.389377

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b175b4bba29'
down_revision: Union[str, None] = 'ec49bde7137a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add partial unique constraint: only one ACTIVE attendance per client
    # This prevents race conditions at the database level
    # The constraint only applies when status = 'ACTIVE'
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_attendances_client_id_active_unique 
        ON attendances (client_id) 
        WHERE status = 'ACTIVE'
    """)


def downgrade() -> None:
    # Remove the partial unique constraint
    op.execute("DROP INDEX IF EXISTS ix_attendances_client_id_active_unique")

