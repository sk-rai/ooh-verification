"""Initial database schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-03-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables for TrustCapture database."""
    
    
    # Create clients table
    op.create_table(
        'clients',
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('subscription_tier', postgresql.ENUM('free', 'pro', 'enterprise', name='subscriptiontier'), nullable=False),
        sa.Column('subscription_status', postgresql.ENUM('active', 'cancelled', 'expired', 'past_due', name='subscriptionstatus'), nullable=False),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('client_id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('stripe_customer_id')
    )
    op.create_index('idx_clients_email', 'clients', ['email'])
    op.create_index('idx_clients_subscription', 'clients', ['subscription_tier', 'subscription_status'])
    
    # Create vendors table
    op.create_table(
        'vendors',
        sa.Column('vendor_id', sa.String(length=6), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('status', postgresql.ENUM('active', 'inactive', name='vendorstatus'), nullable=False),
        sa.Column('created_by_client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('device_id', sa.String(length=255), nullable=True),
        sa.Column('public_key', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_client_id'], ['clients.client_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('vendor_id'),
        sa.UniqueConstraint('device_id')
    )
    op.create_index('idx_vendors_client', 'vendors', ['created_by_client_id'])
    op.create_index('idx_vendors_phone', 'vendors', ['phone_number'])
    op.create_index('idx_vendors_status', 'vendors', ['status'])
    
    # Create campaigns table
    op.create_table(
        'campaigns',
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('campaign_code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('campaign_type', postgresql.ENUM('ooh', 'construction', 'insurance', 'delivery', 'healthcare', 'property_management', name='campaigntype'), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'completed', 'cancelled', name='campaignstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.client_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('campaign_id'),
        sa.UniqueConstraint('campaign_code')
    )
    op.create_index('idx_campaigns_client', 'campaigns', ['client_id'])
    op.create_index('idx_campaigns_code', 'campaigns', ['campaign_code'])
    op.create_index('idx_campaigns_dates', 'campaigns', ['start_date', 'end_date'])
    
    # Create location_profiles table
    op.create_table(
        'location_profiles',
        sa.Column('profile_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('expected_latitude', sa.Float(precision=10), nullable=False),
        sa.Column('expected_longitude', sa.Float(precision=10), nullable=False),
        sa.Column('tolerance_meters', sa.Float(), nullable=False),
        sa.Column('expected_wifi_bssids', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('expected_cell_tower_ids', postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column('expected_pressure_min', sa.Float(), nullable=True),
        sa.Column('expected_pressure_max', sa.Float(), nullable=True),
        sa.Column('expected_light_min', sa.Float(), nullable=True),
        sa.Column('expected_light_max', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.campaign_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('profile_id'),
        sa.UniqueConstraint('campaign_id')
    )
    op.create_index('idx_location_profiles_campaign', 'location_profiles', ['campaign_id'])
    
    # Create campaign_vendor_assignments table
    op.create_table(
        'campaign_vendor_assignments',
        sa.Column('assignment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vendor_id', sa.String(length=6), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.campaign_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.vendor_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('assignment_id'),
        sa.UniqueConstraint('campaign_id', 'vendor_id', name='uq_campaign_vendor')
    )
    op.create_index('idx_assignments_campaign', 'campaign_vendor_assignments', ['campaign_id'])
    op.create_index('idx_assignments_vendor', 'campaign_vendor_assignments', ['vendor_id'])
    
    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tier', postgresql.ENUM('free', 'pro', 'enterprise', name='subscriptiontier'), nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'cancelled', 'expired', 'past_due', name='subscriptionstatus'), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('current_period_start', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('photos_quota', sa.Integer(), nullable=False),
        sa.Column('photos_used', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.client_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('subscription_id'),
        sa.UniqueConstraint('client_id'),
        sa.UniqueConstraint('stripe_subscription_id')
    )
    op.create_index('idx_subscriptions_client', 'subscriptions', ['client_id'])
    
    # Create photos table
    op.create_table(
        'photos',
        sa.Column('photo_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vendor_id', sa.String(length=6), nullable=False),
        sa.Column('capture_timestamp', sa.DateTime(), nullable=False),
        sa.Column('upload_timestamp', sa.DateTime(), nullable=False),
        sa.Column('s3_key', sa.String(length=500), nullable=False),
        sa.Column('thumbnail_s3_key', sa.String(length=500), nullable=True),
        sa.Column('verification_status', postgresql.ENUM('pending', 'verified', 'flagged', 'rejected', name='verificationstatus'), nullable=False),
        sa.Column('signature_valid', sa.Boolean(), nullable=True),
        sa.Column('location_match_score', sa.Float(), nullable=True),
        sa.Column('distance_from_expected', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.campaign_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.vendor_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('photo_id')
    )
    op.create_index('idx_photos_campaign', 'photos', ['campaign_id'])
    op.create_index('idx_photos_vendor', 'photos', ['vendor_id'])
    op.create_index('idx_photos_timestamp', 'photos', ['capture_timestamp'])
    op.create_index('idx_photos_status', 'photos', ['verification_status'])
    
    # Create sensor_data table
    op.create_table(
        'sensor_data',
        sa.Column('sensor_data_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('photo_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('gps_latitude', sa.Float(precision=10), nullable=True),
        sa.Column('gps_longitude', sa.Float(precision=10), nullable=True),
        sa.Column('gps_altitude', sa.Float(), nullable=True),
        sa.Column('gps_accuracy', sa.Float(), nullable=True),
        sa.Column('gps_provider', sa.String(length=20), nullable=True),
        sa.Column('gps_satellite_count', sa.Integer(), nullable=True),
        sa.Column('wifi_networks', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('cell_towers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('barometer_pressure', sa.Float(), nullable=True),
        sa.Column('barometer_altitude', sa.Float(), nullable=True),
        sa.Column('ambient_light_lux', sa.Float(), nullable=True),
        sa.Column('magnetic_field_x', sa.Float(), nullable=True),
        sa.Column('magnetic_field_y', sa.Float(), nullable=True),
        sa.Column('magnetic_field_z', sa.Float(), nullable=True),
        sa.Column('magnetic_field_magnitude', sa.Float(), nullable=True),
        sa.Column('hand_tremor_frequency', sa.Float(), nullable=True),
        sa.Column('hand_tremor_is_human', sa.Boolean(), nullable=True),
        sa.Column('hand_tremor_confidence', sa.Float(), nullable=True),
        sa.Column('location_hash', sa.String(length=64), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('schema_version', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['photo_id'], ['photos.photo_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('sensor_data_id'),
        sa.UniqueConstraint('photo_id')
    )
    op.create_index('idx_sensor_data_photo', 'sensor_data', ['photo_id'])
    op.create_index('idx_sensor_data_gps', 'sensor_data', ['gps_latitude', 'gps_longitude'])
    
    # Create photo_signatures table
    op.create_table(
        'photo_signatures',
        sa.Column('signature_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('photo_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('signature_data', sa.String(), nullable=False),
        sa.Column('algorithm', sa.String(length=50), nullable=False),
        sa.Column('device_id', sa.String(length=255), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('location_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['photo_id'], ['photos.photo_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('signature_id'),
        sa.UniqueConstraint('photo_id')
    )
    op.create_index('idx_signatures_photo', 'photo_signatures', ['photo_id'])


def downgrade() -> None:
    """Drop all tables and enum types."""
    
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_index('idx_signatures_photo', table_name='photo_signatures')
    op.drop_table('photo_signatures')
    
    op.drop_index('idx_sensor_data_gps', table_name='sensor_data')
    op.drop_index('idx_sensor_data_photo', table_name='sensor_data')
    op.drop_table('sensor_data')
    
    op.drop_index('idx_photos_status', table_name='photos')
    op.drop_index('idx_photos_timestamp', table_name='photos')
    op.drop_index('idx_photos_vendor', table_name='photos')
    op.drop_index('idx_photos_campaign', table_name='photos')
    op.drop_table('photos')
    
    op.drop_index('idx_subscriptions_client', table_name='subscriptions')
    op.drop_table('subscriptions')
    
    op.drop_index('idx_assignments_vendor', table_name='campaign_vendor_assignments')
    op.drop_index('idx_assignments_campaign', table_name='campaign_vendor_assignments')
    op.drop_table('campaign_vendor_assignments')
    
    op.drop_index('idx_location_profiles_campaign', table_name='location_profiles')
    op.drop_table('location_profiles')
    
    op.drop_index('idx_campaigns_dates', table_name='campaigns')
    op.drop_index('idx_campaigns_code', table_name='campaigns')
    op.drop_index('idx_campaigns_client', table_name='campaigns')
    op.drop_table('campaigns')
    
    op.drop_index('idx_vendors_status', table_name='vendors')
    op.drop_index('idx_vendors_phone', table_name='vendors')
    op.drop_index('idx_vendors_client', table_name='vendors')
    op.drop_table('vendors')
    
    op.drop_index('idx_clients_subscription', table_name='clients')
    op.drop_index('idx_clients_email', table_name='clients')
    op.drop_table('clients')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS verificationstatus")
    op.execute("DROP TYPE IF EXISTS campaignstatus")
    op.execute("DROP TYPE IF EXISTS campaigntype")
    op.execute("DROP TYPE IF EXISTS vendorstatus")
    op.execute("DROP TYPE IF EXISTS subscriptionstatus")
    op.execute("DROP TYPE IF EXISTS subscriptiontier")
