"""022: Bring vendor_tracks under Alembic control (adopt-not-recreate).

The vendor_tracks table was historically created by a CREATE TABLE IF NOT EXISTS in app/main.py
startup DDL. This migration brings it under Alembic control.

Catalog-driven constraint adoption:
  * If a unique constraint on (vendor_id, track_date) already exists (whatever its name), adopt it.
  * If none exists, create one.
  * The table is created with CREATE TABLE IF NOT EXISTS (idempotent from scratch or with the table present).
  * Missing columns on an existing table are added with ADD COLUMN IF NOT EXISTS.
"""
from alembic import op


revision = '022_vendor_tracks'
down_revision = '021_evidence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")

    # Create the table if absent. If it exists, this is a no-op (adopt).
    op.execute("""
        CREATE TABLE IF NOT EXISTS vendor_tracks (
            track_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            vendor_id VARCHAR(6) NOT NULL,
            track_date DATE NOT NULL,
            points JSONB NOT NULL DEFAULT '[]',
            point_count INTEGER NOT NULL DEFAULT 0,
            total_distance_meters FLOAT,
            start_time TIMESTAMPTZ,
            end_time TIMESTAMPTZ,
            duration_seconds FLOAT,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # Reconcile missing columns on an existing table (adopt-not-recreate).
    op.execute("ALTER TABLE vendor_tracks ADD COLUMN IF NOT EXISTS tenant_id UUID")
    op.execute("ALTER TABLE vendor_tracks ADD COLUMN IF NOT EXISTS vendor_id VARCHAR(6)")
    op.execute("ALTER TABLE vendor_tracks ADD COLUMN IF NOT EXISTS track_date DATE")
    op.execute("ALTER TABLE vendor_tracks ADD COLUMN IF NOT EXISTS points JSONB DEFAULT '[]'")
    op.execute("ALTER TABLE vendor_tracks ADD COLUMN IF NOT EXISTS point_count INTEGER DEFAULT 0")
    op.execute("ALTER TABLE vendor_tracks ADD COLUMN IF NOT EXISTS total_distance_meters FLOAT")
    op.execute("ALTER TABLE vendor_tracks ADD COLUMN IF NOT EXISTS start_time TIMESTAMPTZ")
    op.execute("ALTER TABLE vendor_tracks ADD COLUMN IF NOT EXISTS end_time TIMESTAMPTZ")
    op.execute("ALTER TABLE vendor_tracks ADD COLUMN IF NOT EXISTS duration_seconds FLOAT")
    op.execute("ALTER TABLE vendor_tracks ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active'")
    op.execute("ALTER TABLE vendor_tracks ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now()")
    op.execute("ALTER TABLE vendor_tracks ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()")

    # Catalog-driven unique constraint adoption: if one already exists (whatever its name), adopt it.
    op.execute("""
        DO $$
        DECLARE
            has_constraint boolean;
        BEGIN
            SELECT EXISTS (
                SELECT 1 FROM pg_constraint co
                WHERE co.conrelid = to_regclass('vendor_tracks')
                  AND co.contype = 'u'
                  AND co.conkey = ARRAY[
                      (SELECT a.attnum FROM pg_attribute a
                       WHERE a.attrelid = co.conrelid AND a.attname = 'vendor_id' AND NOT a.attisdropped),
                      (SELECT a.attnum FROM pg_attribute a
                       WHERE a.attrelid = co.conrelid AND a.attname = 'track_date' AND NOT a.attisdropped)
                  ]
            ) INTO has_constraint;
            IF NOT has_constraint THEN
                EXECUTE 'ALTER TABLE vendor_tracks ADD CONSTRAINT uq_vendor_track_date UNIQUE (vendor_id, track_date)';
            END IF;
        END$$
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_vendor_tracks_vendor_date ON vendor_tracks (vendor_id, track_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vendor_tracks_tenant ON vendor_tracks (tenant_id)")


def downgrade() -> None:
    op.drop_table('vendor_tracks')
