"""add_initial_message_to_clients

Revision ID: 2aaa135525bd
Revises: b2c3d4e5f6g7
Create Date: 2026-02-10 13:48:22.422810

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2aaa135525bd'
down_revision: Union[str, None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add initial_message column to clients table
    op.add_column('clients', sa.Column('initial_message', sa.Text(), nullable=True, comment='First message from the client (used for AI classification)'))


def downgrade() -> None:
    # Remove initial_message column from clients table
    op.drop_column('clients', 'initial_message')
