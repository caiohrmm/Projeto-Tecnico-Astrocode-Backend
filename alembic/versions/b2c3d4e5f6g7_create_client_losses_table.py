"""Create client_losses table

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-09 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create client_losses table
    op.create_table(
        'client_losses',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        # Relationships
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('property_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('broker_id', postgresql.UUID(as_uuid=True), nullable=True),
        # Loss details
        sa.Column('loss_reason', sa.String(50), nullable=False),
        sa.Column('loss_stage', sa.String(30), nullable=False),
        # Detailed information
        sa.Column('detailed_reason', sa.Text(), nullable=True, comment='Detailed explanation of why the deal was lost'),
        sa.Column('client_feedback', sa.Text(), nullable=True, comment='Direct feedback from the client'),
        sa.Column('competitor_info', sa.Text(), nullable=True, comment='Information about competitor if applicable'),
        # Analysis fields
        sa.Column('could_have_been_prevented', sa.Boolean(), nullable=True, comment='Whether this loss could have been prevented'),
        sa.Column('lessons_learned', sa.Text(), nullable=True, comment='Lessons learned from this loss'),
        # AI fields
        sa.Column('ai_analysis', sa.Text(), nullable=True, comment='AI-generated analysis of the loss'),
        sa.Column('ai_recommendations', sa.Text(), nullable=True, comment='AI recommendations to prevent similar losses'),
        # Metadata
        sa.Column('additional_data', postgresql.JSONB(), nullable=True, comment='Additional structured data about the loss'),
        # Timestamps
        sa.Column('lost_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='When the client was lost'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        # Foreign keys
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['broker_id'], ['users.id'], ondelete='SET NULL'),
    )

    # Create indexes
    op.create_index('ix_client_losses_id', 'client_losses', ['id'])
    op.create_index('ix_client_losses_client_id', 'client_losses', ['client_id'])
    op.create_index('ix_client_losses_property_id', 'client_losses', ['property_id'])
    op.create_index('ix_client_losses_broker_id', 'client_losses', ['broker_id'])
    op.create_index('ix_client_losses_loss_reason', 'client_losses', ['loss_reason'])
    op.create_index('ix_client_losses_loss_stage', 'client_losses', ['loss_stage'])
    op.create_index('ix_client_losses_created_at', 'client_losses', ['created_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_client_losses_created_at', table_name='client_losses')
    op.drop_index('ix_client_losses_loss_stage', table_name='client_losses')
    op.drop_index('ix_client_losses_loss_reason', table_name='client_losses')
    op.drop_index('ix_client_losses_broker_id', table_name='client_losses')
    op.drop_index('ix_client_losses_property_id', table_name='client_losses')
    op.drop_index('ix_client_losses_client_id', table_name='client_losses')
    op.drop_index('ix_client_losses_id', table_name='client_losses')
    
    # Drop table
    op.drop_table('client_losses')

