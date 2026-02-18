"""Backfill visibility_score for existing properties.

Uses the visibility_score_service to calculate and set scores for all properties
that have NULL visibility_score. Run after deployment to ensure existing
properties are ranked in the listing.
"""
from alembic import op
from sqlalchemy.orm import Session

# Revision identifiers
revision = "e1f2a3b4c5d6"
down_revision = "a1b2c3d4e5f7"  # remove_channel_from_attendances
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Calculate and set visibility_score for all properties with NULL score."""
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        from app.properties.models import Property
        from app.properties.visibility_score_service import calculate_visibility_score

        properties = session.query(Property).filter(Property.visibility_score.is_(None)).all()
        for prop in properties:
            prop.visibility_score = calculate_visibility_score(prop)
        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    """No downgrade - we don't clear scores on rollback."""
    pass
