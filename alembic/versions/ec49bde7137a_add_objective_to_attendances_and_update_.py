"""add_objective_to_attendances_and_update_status_enum

Revision ID: ec49bde7137a
Revises: 3d3cdc7c611e
Create Date: 2026-02-11 02:19:02.091626

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec49bde7137a'
down_revision: Union[str, None] = '3d3cdc7c611e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add objective column to attendances table
    op.add_column(
        'attendances',
        sa.Column(
            'objective',
            sa.Text(),
            nullable=True,
            comment="Clear objective of this interaction cycle (e.g., 'Purchase residential property in City X')"
        )
    )
    
    # Update AttendanceStatus enum
    # Since there's no data in the table, we can safely drop and recreate the enum
    # Step 1: Convert column to text temporarily
    op.execute("ALTER TABLE attendances ALTER COLUMN status TYPE VARCHAR(20) USING status::text")
    
    # Step 2: Drop the old enum type
    op.execute("DROP TYPE IF EXISTS attendancestatus")
    
    # Step 3: Create new enum type with new values
    op.execute("CREATE TYPE attendancestatus AS ENUM ('ACTIVE', 'COMPLETED', 'LOST', 'ABANDONED')")
    
    # Step 4: Convert column back to enum type
    op.execute("ALTER TABLE attendances ALTER COLUMN status TYPE attendancestatus USING status::attendancestatus")
    
    # Step 5: Set default value to ACTIVE
    op.execute("ALTER TABLE attendances ALTER COLUMN status SET DEFAULT 'ACTIVE'::attendancestatus")


def downgrade() -> None:
    # Revert status enum to old values
    op.execute("ALTER TABLE attendances ALTER COLUMN status TYPE VARCHAR(20)")
    op.execute("DROP TYPE IF EXISTS attendancestatus")
    op.execute("CREATE TYPE attendancestatus AS ENUM ('IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'PAUSED')")
    op.execute("ALTER TABLE attendances ALTER COLUMN status TYPE attendancestatus USING status::text::attendancestatus")
    op.execute("ALTER TABLE attendances ALTER COLUMN status SET DEFAULT 'IN_PROGRESS'::attendancestatus")
    
    # Remove objective column
    op.drop_column('attendances', 'objective')

