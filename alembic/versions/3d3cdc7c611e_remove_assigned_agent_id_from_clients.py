"""remove_assigned_agent_id_from_clients

Revision ID: 3d3cdc7c611e
Revises: 2aaa135525bd
Create Date: 2026-02-10 14:15:29.097039

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3d3cdc7c611e'
down_revision: Union[str, None] = '2aaa135525bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove assigned_agent_id column from clients table
    op.drop_index(op.f('ix_clients_assigned_agent_id'), table_name='clients')
    op.drop_constraint(op.f('fk_clients_assigned_agent_id'), 'clients', type_='foreignkey')
    op.drop_column('clients', 'assigned_agent_id')


def downgrade() -> None:
    # Restore assigned_agent_id column to clients table
    op.add_column('clients', sa.Column('assigned_agent_id', sa.UUID(), autoincrement=False, nullable=True))
    op.create_foreign_key(op.f('fk_clients_assigned_agent_id'), 'clients', 'users', ['assigned_agent_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_clients_assigned_agent_id'), 'clients', ['assigned_agent_id'], unique=False)
