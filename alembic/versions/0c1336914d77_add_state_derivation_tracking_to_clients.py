"""add_state_derivation_tracking_to_clients

Revision ID: 0c1336914d77
Revises: 1b175b4bba29
Create Date: 2026-02-11 18:16:34.256913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0c1336914d77'
down_revision: Union[str, None] = '1b175b4bba29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add state derivation tracking columns to clients table
    op.add_column(
        'clients',
        sa.Column(
            'last_state_derivation_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Timestamp of last automatic state derivation from AI signals'
        )
    )
    op.add_column(
        'clients',
        sa.Column(
            'state_derivation_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='Number of times client state was automatically derived from AI signals'
        )
    )
    op.add_column(
        'clients',
        sa.Column(
            'state_derived_from_attendances_count',
            sa.Integer(),
            nullable=True,
            comment='Number of attendances used in the last state derivation'
        )
    )


def downgrade() -> None:
    # Remove state derivation tracking columns
    op.drop_column('clients', 'state_derived_from_attendances_count')
    op.drop_column('clients', 'state_derivation_count')
    op.drop_column('clients', 'last_state_derivation_at')
    op.create_index(op.f('ix_attendances_client_id_active_unique'), 'attendances', ['client_id'], unique=True, postgresql_where="(status = 'ACTIVE'::attendancestatus)")
    op.alter_column('attendances', 'status',
               existing_type=sa.Enum('ACTIVE', 'COMPLETED', 'LOST', 'ABANDONED', name='attendancestatus', native_enum=False, length=20),
               type_=postgresql.ENUM('ACTIVE', 'COMPLETED', 'LOST', 'ABANDONED', name='attendancestatus'),
               existing_nullable=False,
               existing_server_default=sa.text("'ACTIVE'::attendancestatus"))
    op.alter_column('attendances', 'raw_content',
               existing_type=sa.TEXT(),
               comment=None,
               existing_comment='Raw content of conversations (can accumulate over time within the same cycle)',
               existing_nullable=False)
    op.drop_index(op.f('ix_ai_summaries_attendance_id'), table_name='ai_summaries')
    op.create_index(op.f('ix_ai_summaries_attendance_id'), 'ai_summaries', ['attendance_id'], unique=False)
    op.alter_column('ai_summaries', 'recommended_properties',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               comment='Array of recommended property IDs based on client preferences',
               existing_comment='Array of recommended property IDs based on client preferences extracted from attendance',
               existing_nullable=True)
    op.alter_column('ai_summaries', 'attendance_id',
               existing_type=sa.UUID(),
               comment=None,
               existing_comment='One AI summary per attendance (unique constraint)',
               existing_nullable=False)
    op.create_table('sales',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('client_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('property_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('broker_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('sale_type', sa.VARCHAR(length=20), autoincrement=False, nullable=False),
    sa.Column('status', sa.VARCHAR(length=20), server_default=sa.text("'PENDING'::character varying"), autoincrement=False, nullable=False),
    sa.Column('sale_value', sa.NUMERIC(precision=15, scale=2), autoincrement=False, nullable=False, comment='Total sale value or monthly rent value'),
    sa.Column('commission_percentage', sa.NUMERIC(precision=5, scale=2), server_default=sa.text('5.00'), autoincrement=False, nullable=True, comment='Commission percentage (default 5%)'),
    sa.Column('commission_value', sa.NUMERIC(precision=15, scale=2), autoincrement=False, nullable=True, comment='Calculated commission value'),
    sa.Column('down_payment', sa.NUMERIC(precision=15, scale=2), autoincrement=False, nullable=True, comment='Down payment amount'),
    sa.Column('payment_method', sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    sa.Column('rent_duration_months', sa.INTEGER(), autoincrement=False, nullable=True, comment='Duration of rent contract in months'),
    sa.Column('rent_start_date', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('proposal_date', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True, comment='When the proposal was accepted'),
    sa.Column('contract_date', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True, comment='When the contract was signed'),
    sa.Column('completion_date', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True, comment='When the deal was completed'),
    sa.Column('notes', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('ai_analysis', sa.TEXT(), autoincrement=False, nullable=True, comment='AI-generated analysis of the sale'),
    sa.Column('ai_success_factors', sa.TEXT(), autoincrement=False, nullable=True, comment='AI-detected factors that led to success'),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['broker_id'], ['users.id'], name=op.f('sales_broker_id_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], name=op.f('sales_client_id_fkey'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['property_id'], ['properties.id'], name=op.f('sales_property_id_fkey'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('sales_pkey'))
    )
    op.create_index(op.f('ix_sales_status'), 'sales', ['status'], unique=False)
    op.create_index(op.f('ix_sales_sale_type'), 'sales', ['sale_type'], unique=False)
    op.create_index(op.f('ix_sales_property_id'), 'sales', ['property_id'], unique=False)
    op.create_index(op.f('ix_sales_id'), 'sales', ['id'], unique=False)
    op.create_index(op.f('ix_sales_created_at'), 'sales', ['created_at'], unique=False)
    op.create_index(op.f('ix_sales_client_id'), 'sales', ['client_id'], unique=False)
    op.create_index(op.f('ix_sales_broker_id'), 'sales', ['broker_id'], unique=False)
    op.create_table('client_losses',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('client_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('property_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('broker_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('loss_reason', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('loss_stage', sa.VARCHAR(length=30), autoincrement=False, nullable=False),
    sa.Column('detailed_reason', sa.TEXT(), autoincrement=False, nullable=True, comment='Detailed explanation of why the deal was lost'),
    sa.Column('client_feedback', sa.TEXT(), autoincrement=False, nullable=True, comment='Direct feedback from the client'),
    sa.Column('competitor_info', sa.TEXT(), autoincrement=False, nullable=True, comment='Information about competitor if applicable'),
    sa.Column('could_have_been_prevented', sa.BOOLEAN(), autoincrement=False, nullable=True, comment='Whether this loss could have been prevented'),
    sa.Column('lessons_learned', sa.TEXT(), autoincrement=False, nullable=True, comment='Lessons learned from this loss'),
    sa.Column('ai_analysis', sa.TEXT(), autoincrement=False, nullable=True, comment='AI-generated analysis of the loss'),
    sa.Column('ai_recommendations', sa.TEXT(), autoincrement=False, nullable=True, comment='AI recommendations to prevent similar losses'),
    sa.Column('additional_data', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True, comment='Additional structured data about the loss'),
    sa.Column('lost_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False, comment='When the client was lost'),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['broker_id'], ['users.id'], name=op.f('client_losses_broker_id_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], name=op.f('client_losses_client_id_fkey'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['property_id'], ['properties.id'], name=op.f('client_losses_property_id_fkey'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('client_losses_pkey'))
    )
    op.create_index(op.f('ix_client_losses_property_id'), 'client_losses', ['property_id'], unique=False)
    op.create_index(op.f('ix_client_losses_loss_stage'), 'client_losses', ['loss_stage'], unique=False)
    op.create_index(op.f('ix_client_losses_loss_reason'), 'client_losses', ['loss_reason'], unique=False)
    op.create_index(op.f('ix_client_losses_id'), 'client_losses', ['id'], unique=False)
    op.create_index(op.f('ix_client_losses_created_at'), 'client_losses', ['created_at'], unique=False)
    op.create_index(op.f('ix_client_losses_client_id'), 'client_losses', ['client_id'], unique=False)
    op.create_index(op.f('ix_client_losses_broker_id'), 'client_losses', ['broker_id'], unique=False)
    op.create_table('client_timeline',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('client_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('event_type', sa.VARCHAR(length=30), autoincrement=False, nullable=False),
    sa.Column('title', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('event_data', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True, comment='Event-specific data'),
    sa.Column('related_attendance_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('related_visit_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('related_property_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('created_by_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('ai_generated', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.Column('importance', sa.INTEGER(), autoincrement=False, nullable=False, comment='Importance level 1-5'),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], name=op.f('client_timeline_client_id_fkey'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('client_timeline_created_by_id_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['related_attendance_id'], ['attendances.id'], name=op.f('client_timeline_related_attendance_id_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['related_property_id'], ['properties.id'], name=op.f('client_timeline_related_property_id_fkey'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['related_visit_id'], ['visits.id'], name=op.f('client_timeline_related_visit_id_fkey'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('client_timeline_pkey'))
    )
    op.create_index(op.f('ix_client_timeline_related_visit_id'), 'client_timeline', ['related_visit_id'], unique=False)
    op.create_index(op.f('ix_client_timeline_related_property_id'), 'client_timeline', ['related_property_id'], unique=False)
    op.create_index(op.f('ix_client_timeline_related_attendance_id'), 'client_timeline', ['related_attendance_id'], unique=False)
    op.create_index(op.f('ix_client_timeline_event_type'), 'client_timeline', ['event_type'], unique=False)
    op.create_index(op.f('ix_client_timeline_created_by_id'), 'client_timeline', ['created_by_id'], unique=False)
    op.create_index(op.f('ix_client_timeline_created_at'), 'client_timeline', ['created_at'], unique=False)
    op.create_index(op.f('ix_client_timeline_client_id'), 'client_timeline', ['client_id'], unique=False)
    op.create_index(op.f('ix_client_timeline_client_event'), 'client_timeline', ['client_id', 'event_type'], unique=False)
    op.create_index(op.f('ix_client_timeline_client_date'), 'client_timeline', ['client_id', 'created_at'], unique=False)
    # ### end Alembic commands ###

