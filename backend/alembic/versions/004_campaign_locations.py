"""add campaign_locations table

Revision ID: 004_campaign_locations
Revises: 003_subscription_enhancements
Create Date: 2026-03-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_campaign_locations'
down_revision = '003_subscription_enhancements'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create campaign_locations table."""
    op.create_table(
        'campaign_locations',
        sa.Column('location_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('address', sa.String(500), nullable=False),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('postal_code', sa.String(20), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('verification_radius_meters', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('geocoding_accuracy', sa.String(50), nullable=True),
        sa.Column('place_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.campaign_id'], ondelete='CASCADE'),
    )
    
    # Create indexes
    op.create_index('ix_campaign_locations_location_id', 'campaign_locations', ['location_id'])
    op.create_index('ix_campaign_locations_campaign_id', 'campaign_locations', ['campaign_id'])
    op.create_index('ix_campaign_locations_latitude', 'campaign_locations', ['latitude'])
    op.create_index('ix_campaign_locations_longitude', 'campaign_locations', ['longitude'])
    
    # Create composite index for geospatial queries
    op.create_index('ix_campaign_locations_coords', 'campaign_locations', ['latitude', 'longitude'])


def downgrade() -> None:
    """Drop campaign_locations table."""
    op.drop_index('ix_campaign_locations_coords', table_name='campaign_locations')
    op.drop_index('ix_campaign_locations_longitude', table_name='campaign_locations')
    op.drop_index('ix_campaign_locations_latitude', table_name='campaign_locations')
    op.drop_index('ix_campaign_locations_campaign_id', table_name='campaign_locations')
    op.drop_index('ix_campaign_locations_location_id', table_name='campaign_locations')
    op.drop_table('campaign_locations')
