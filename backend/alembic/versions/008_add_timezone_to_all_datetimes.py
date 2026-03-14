"""Convert all DateTime columns to TIMESTAMP WITH TIME ZONE

Revision ID: 008_add_timezone_to_all_datetimes
Revises: 007_campaign_vendor_enhancements
"""
from alembic import op
import sqlalchemy as sa

revision = '008_add_timezone_to_all_datetimes'
down_revision = '007_campaign_vendor_enhancements'
branch_labels = None
depends_on = None


def upgrade():
    # campaigns
    op.alter_column('campaigns', 'start_date', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('campaigns', 'end_date', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('campaigns', 'created_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('campaigns', 'updated_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())

    # campaign_locations
    op.alter_column('campaign_locations', 'created_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('campaign_locations', 'updated_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())

    # campaign_vendor_assignments
    op.alter_column('campaign_vendor_assignments', 'assigned_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('campaign_vendor_assignments', 'created_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('campaign_vendor_assignments', 'updated_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())

    # clients
    op.alter_column('clients', 'created_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('clients', 'updated_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())

    # location_profiles
    op.alter_column('location_profiles', 'created_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('location_profiles', 'updated_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())

    # photos
    op.alter_column('photos', 'capture_timestamp', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('photos', 'upload_timestamp', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('photos', 'created_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())

    # photo_signatures
    op.alter_column('photo_signatures', 'timestamp', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('photo_signatures', 'created_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())

    # sensor_data
    op.alter_column('sensor_data', 'created_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())

    # subscriptions
    op.alter_column('subscriptions', 'current_period_start', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('subscriptions', 'current_period_end', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('subscriptions', 'trial_end_date', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('subscriptions', 'cancellation_date', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('subscriptions', 'created_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('subscriptions', 'updated_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())

    # tenant_config
    op.alter_column('tenant_config', 'created_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('tenant_config', 'updated_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())

    # vendors
    op.alter_column('vendors', 'created_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('vendors', 'last_login_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column('vendors', 'updated_at', type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())


def downgrade():
    tables_columns = {
        'campaigns': ['start_date', 'end_date', 'created_at', 'updated_at'],
        'campaign_locations': ['created_at', 'updated_at'],
        'campaign_vendor_assignments': ['assigned_at', 'created_at', 'updated_at'],
        'clients': ['created_at', 'updated_at'],
        'location_profiles': ['created_at', 'updated_at'],
        'photos': ['capture_timestamp', 'upload_timestamp', 'created_at'],
        'photo_signatures': ['timestamp', 'created_at'],
        'sensor_data': ['created_at'],
        'subscriptions': ['current_period_start', 'current_period_end', 'trial_end_date', 'cancellation_date', 'created_at', 'updated_at'],
        'tenant_config': ['created_at', 'updated_at'],
        'vendors': ['created_at', 'last_login_at', 'updated_at'],
    }
    for table, columns in tables_columns.items():
        for col in columns:
            op.alter_column(table, col, type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True))
