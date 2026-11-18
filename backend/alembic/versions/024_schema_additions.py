"""024: Bring startup-DDL columns under Alembic control.

These columns were added by ALTER TABLE ... ADD COLUMN IF NOT EXISTS in app/main.py startup DDL.
Now they are migration-owned. Idempotent from scratch or with the columns already present.

Covers:
  * evidence.signing_key_id, signing_key_fingerprint, signature_outcome
  * clients.report_settings
  * location_profiles geofence columns (geofence_type, viewport_*, polygon_points, corridor_buffer_meters, geocode_accuracy)

Note: asset_id, asset_type, location_description on location_profiles are already in migration 021.
"""
from alembic import op


revision = '024_schema_additions'
down_revision = '023_api_keys_device_keys'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")

    # evidence signing columns
    op.execute("ALTER TABLE evidence ADD COLUMN IF NOT EXISTS signing_key_id UUID")
    op.execute("ALTER TABLE evidence ADD COLUMN IF NOT EXISTS signing_key_fingerprint VARCHAR(64)")
    op.execute("ALTER TABLE evidence ADD COLUMN IF NOT EXISTS signature_outcome VARCHAR(30)")

    # clients.report_settings
    op.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS report_settings JSONB")

    # location_profiles geofence columns
    op.execute("ALTER TABLE location_profiles ADD COLUMN IF NOT EXISTS geofence_type VARCHAR(20) DEFAULT 'circle'")
    op.execute("ALTER TABLE location_profiles ADD COLUMN IF NOT EXISTS viewport_ne_lat FLOAT")
    op.execute("ALTER TABLE location_profiles ADD COLUMN IF NOT EXISTS viewport_ne_lon FLOAT")
    op.execute("ALTER TABLE location_profiles ADD COLUMN IF NOT EXISTS viewport_sw_lat FLOAT")
    op.execute("ALTER TABLE location_profiles ADD COLUMN IF NOT EXISTS viewport_sw_lon FLOAT")
    op.execute("ALTER TABLE location_profiles ADD COLUMN IF NOT EXISTS polygon_points JSONB")
    op.execute("ALTER TABLE location_profiles ADD COLUMN IF NOT EXISTS corridor_buffer_meters FLOAT")
    op.execute("ALTER TABLE location_profiles ADD COLUMN IF NOT EXISTS geocode_accuracy VARCHAR(20)")


def downgrade() -> None:
    op.execute("ALTER TABLE location_profiles DROP COLUMN IF EXISTS geocode_accuracy")
    op.execute("ALTER TABLE location_profiles DROP COLUMN IF EXISTS corridor_buffer_meters")
    op.execute("ALTER TABLE location_profiles DROP COLUMN IF EXISTS polygon_points")
    op.execute("ALTER TABLE location_profiles DROP COLUMN IF EXISTS viewport_sw_lon")
    op.execute("ALTER TABLE location_profiles DROP COLUMN IF EXISTS viewport_sw_lat")
    op.execute("ALTER TABLE location_profiles DROP COLUMN IF EXISTS viewport_ne_lon")
    op.execute("ALTER TABLE location_profiles DROP COLUMN IF EXISTS viewport_ne_lat")
    op.execute("ALTER TABLE location_profiles DROP COLUMN IF EXISTS geofence_type")
    op.execute("ALTER TABLE clients DROP COLUMN IF EXISTS report_settings")
    op.execute("ALTER TABLE evidence DROP COLUMN IF EXISTS signature_outcome")
    op.execute("ALTER TABLE evidence DROP COLUMN IF EXISTS signing_key_fingerprint")
    op.execute("ALTER TABLE evidence DROP COLUMN IF EXISTS signing_key_id")
