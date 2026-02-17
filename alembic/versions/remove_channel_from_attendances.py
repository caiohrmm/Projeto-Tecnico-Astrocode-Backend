"""remove_channel_from_attendances

Revision ID: a1b2c3d4e5f7
Revises: f9f941464dbb
Create Date: 2026-02-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = 'f9f941464dbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove channel column and its index from attendances table
    op.drop_index(op.f('ix_attendances_channel'), table_name='attendances')
    op.drop_column('attendances', 'channel')
    # Drop the enum type if it's no longer used
    # Note: PostgreSQL will keep the enum type even after dropping the column
    # If you want to remove it completely, uncomment the line below
    # op.execute("DROP TYPE IF EXISTS attendancechannel")


def downgrade() -> None:
    # Restore channel column to attendances table
    op.add_column('attendances', sa.Column('channel', sa.Enum('WHATSAPP', 'SITE', 'PHONE', 'EMAIL', 'IN_PERSON', name='attendancechannel', native_enum=False, length=20), nullable=False, server_default='WHATSAPP'))
    op.create_index(op.f('ix_attendances_channel'), 'attendances', ['channel'], unique=False)

