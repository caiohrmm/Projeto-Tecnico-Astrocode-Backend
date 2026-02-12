"""remove_started_at_ended_at_duration_from_attendances

Revision ID: 357cfb238719
Revises: 0c1336914d77
Create Date: 2026-02-11 22:32:01.911844

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '357cfb238719'
down_revision: Union[str, None] = '0c1336914d77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove started_at, ended_at, and duration columns from attendances table
    op.drop_index(op.f('ix_attendances_started_at'), table_name='attendances')
    op.drop_column('attendances', 'duration')
    op.drop_column('attendances', 'ended_at')
    op.drop_column('attendances', 'started_at')


def downgrade() -> None:
    # Restore started_at, ended_at, and duration columns to attendances table
    op.add_column('attendances', sa.Column('started_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False, server_default=sa.text('now()')))
    op.add_column('attendances', sa.Column('ended_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))
    op.add_column('attendances', sa.Column('duration', sa.INTEGER(), autoincrement=False, nullable=True, comment='Duration in seconds, calculated automatically when ended_at is set'))
    op.create_index(op.f('ix_attendances_started_at'), 'attendances', ['started_at'], unique=False)

