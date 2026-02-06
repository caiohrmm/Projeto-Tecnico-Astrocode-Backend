"""add_recommended_properties_to_ai_summaries

Revision ID: d68658a76e25
Revises: d10f16e5ec7a
Create Date: 2026-02-05 23:45:09.531913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd68658a76e25'
down_revision: Union[str, None] = 'd10f16e5ec7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add recommended_properties column as JSONB array of UUIDs
    op.add_column('ai_summaries',
        sa.Column('recommended_properties', sa.dialects.postgresql.JSONB(), nullable=True,
                  comment='Array of recommended property IDs based on client preferences')
    )


def downgrade() -> None:
    # Remove recommended_properties column
    op.drop_column('ai_summaries', 'recommended_properties')

