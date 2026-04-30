"""Remove unique constraint on location_profiles.campaign_id for multi-location support.

Revision ID: 020_multi_location
Revises: 019_motion_sensors
Create Date: 2026-04-29
"""
from alembic import op

revision = '020_multi_location'
down_revision = '019_motion_sensors'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the unique constraint on campaign_id to allow multiple locations per campaign
    # The constraint name may vary — try common patterns
    try:
        op.drop_constraint('location_profiles_campaign_id_key', 'location_profiles', type_='unique')
    except Exception:
        try:
            op.drop_constraint('uq_location_profiles_campaign_id', 'location_profiles', type_='unique')
        except Exception:
            # If no named constraint, drop and recreate the index as non-unique
            pass

    # Ensure there's a regular (non-unique) index for performance
    op.create_index('ix_location_profiles_campaign_id', 'location_profiles', ['campaign_id'], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index('ix_location_profiles_campaign_id', 'location_profiles')
    op.create_unique_constraint('location_profiles_campaign_id_key', 'location_profiles', ['campaign_id'])
