"""Add SALE_COMPLETED and LOSS_REGISTERED to detectedintent enum.

Revision ID: add_sale_loss_intents
Revises: d68658a76e25
Create Date: 2025-02-18

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'add_sale_loss_intents'
down_revision = 'd68658a76e25'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new values to PostgreSQL enum (IF NOT EXISTS to allow re-running)
    op.execute("ALTER TYPE detectedintent ADD VALUE IF NOT EXISTS 'SALE_COMPLETED'")
    op.execute("ALTER TYPE detectedintent ADD VALUE IF NOT EXISTS 'LOSS_REGISTERED'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values easily.
    # The column stores varchar(30), so old data with these values would need manual cleanup.
    # For safety, we leave the enum values in place on downgrade.
    pass
