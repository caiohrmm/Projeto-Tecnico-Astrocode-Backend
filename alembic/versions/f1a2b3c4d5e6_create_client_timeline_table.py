"""Create client_timeline table

Revision ID: f1a2b3c4d5e6
Revises: d68658a76e25
Create Date: 2026-02-09 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'd68658a76e25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'client_timeline',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('event_type', sa.String(30), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('event_data', postgresql.JSONB, nullable=True, comment='Event-specific data'),
        sa.Column('related_attendance_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('attendances.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('related_visit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('related_property_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('properties.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('ai_generated', sa.Boolean, nullable=False, default=False),
        sa.Column('importance', sa.Integer, nullable=False, default=3, comment='Importance level 1-5'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )
    
    # Create indexes for efficient queries
    op.create_index('ix_client_timeline_client_event', 'client_timeline', ['client_id', 'event_type'])
    op.create_index('ix_client_timeline_client_date', 'client_timeline', ['client_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_client_timeline_client_date', table_name='client_timeline')
    op.drop_index('ix_client_timeline_client_event', table_name='client_timeline')
    op.drop_table('client_timeline')

