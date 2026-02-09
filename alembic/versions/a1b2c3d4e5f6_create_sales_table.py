"""Create sales table

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-02-09 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sales table
    op.create_table(
        'sales',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        # Relationships
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('property_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('broker_id', postgresql.UUID(as_uuid=True), nullable=True),
        # Sale details
        sa.Column('sale_type', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),
        # Financial
        sa.Column('sale_value', sa.Numeric(15, 2), nullable=False, comment='Total sale value or monthly rent value'),
        sa.Column('commission_percentage', sa.Numeric(5, 2), nullable=True, server_default='5.00', comment='Commission percentage (default 5%)'),
        sa.Column('commission_value', sa.Numeric(15, 2), nullable=True, comment='Calculated commission value'),
        sa.Column('down_payment', sa.Numeric(15, 2), nullable=True, comment='Down payment amount'),
        sa.Column('payment_method', sa.String(20), nullable=True),
        # Rent specific
        sa.Column('rent_duration_months', sa.Integer(), nullable=True, comment='Duration of rent contract in months'),
        sa.Column('rent_start_date', sa.DateTime(timezone=True), nullable=True),
        # Timeline
        sa.Column('proposal_date', sa.DateTime(timezone=True), nullable=True, comment='When the proposal was accepted'),
        sa.Column('contract_date', sa.DateTime(timezone=True), nullable=True, comment='When the contract was signed'),
        sa.Column('completion_date', sa.DateTime(timezone=True), nullable=True, comment='When the deal was completed'),
        # Notes and AI
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('ai_analysis', sa.Text(), nullable=True, comment='AI-generated analysis of the sale'),
        sa.Column('ai_success_factors', sa.Text(), nullable=True, comment='AI-detected factors that led to success'),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        # Foreign keys
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['broker_id'], ['users.id'], ondelete='SET NULL'),
    )

    # Create indexes
    op.create_index('ix_sales_id', 'sales', ['id'])
    op.create_index('ix_sales_client_id', 'sales', ['client_id'])
    op.create_index('ix_sales_property_id', 'sales', ['property_id'])
    op.create_index('ix_sales_broker_id', 'sales', ['broker_id'])
    op.create_index('ix_sales_sale_type', 'sales', ['sale_type'])
    op.create_index('ix_sales_status', 'sales', ['status'])
    op.create_index('ix_sales_created_at', 'sales', ['created_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_sales_created_at', table_name='sales')
    op.drop_index('ix_sales_status', table_name='sales')
    op.drop_index('ix_sales_sale_type', table_name='sales')
    op.drop_index('ix_sales_broker_id', table_name='sales')
    op.drop_index('ix_sales_property_id', table_name='sales')
    op.drop_index('ix_sales_client_id', table_name='sales')
    op.drop_index('ix_sales_id', table_name='sales')
    
    # Drop table
    op.drop_table('sales')

