"""Convert all DateTime columns to TIMESTAMP WITH TIME ZONE

Revision ID: 008_add_timezone_to_all_datetimes
Revises: 007_campaign_vendor_enhancements
"""
from alembic import op

revision = '008_add_timezone_to_all_datetimes'
down_revision = '007_campaign_vendor_enhancements'
branch_labels = None
depends_on = None

TABLES_COLUMNS = {
    'campaigns': ['start_date', 'end_date', 'created_at', 'updated_at'],
    'campaign_locations': ['created_at', 'updated_at'],
    'campaign_vendor_assignments': ['assigned_at', 'created_at', 'updated_at'],
    'clients': ['created_at', 'updated_at'],
    'location_profiles': ['created_at', 'updated_at'],
    'photos': ['capture_timestamp', 'upload_timestamp', 'created_at'],
    'photo_signatures': ['timestamp', 'created_at'],
    'sensor_data': ['created_at'],
    'subscriptions': [
        'current_period_start', 'current_period_end',
        'trial_end_date', 'cancellation_date',
        'created_at', 'updated_at',
    ],
    'tenant_config': ['created_at', 'updated_at'],
    'vendors': ['created_at', 'last_login_at', 'updated_at'],
}


def _tz_sql(table, col):
    q = chr(39)
    return (
        "DO $$ BEGIN "
        "IF EXISTS ("
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name=" + q + table + q
        + " AND column_name=" + q + col + q
        + " AND data_type != " + q + "timestamp with time zone" + q
        + ") THEN "
        "ALTER TABLE " + table + " ALTER COLUMN " + col
        + " TYPE TIMESTAMP WITH TIME ZONE; "
        "END IF; "
        "END $$;"
    )


def _untz_sql(table, col):
    q = chr(39)
    return (
        "DO $$ BEGIN "
        "IF EXISTS ("
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name=" + q + table + q
        + " AND column_name=" + q + col + q
        + " AND data_type = " + q + "timestamp with time zone" + q
        + ") THEN "
        "ALTER TABLE " + table + " ALTER COLUMN " + col
        + " TYPE TIMESTAMP WITHOUT TIME ZONE; "
        "END IF; "
        "END $$;"
    )


def upgrade():
    for table, columns in TABLES_COLUMNS.items():
        for col in columns:
            op.execute(_tz_sql(table, col))


def downgrade():
    for table, columns in TABLES_COLUMNS.items():
        for col in columns:
            op.execute(_untz_sql(table, col))
