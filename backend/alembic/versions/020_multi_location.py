"""Remove unique constraint on location_profiles.campaign_id for multi-location support.

Revision ID: 020_multi_location
Revises: 019_motion_sensors
Create Date: 2026-04-29

M1 repair (migration-drift): the old code wrapped op.drop_constraint in try/except. On PostgreSQL a failed statement
aborts the whole transaction, so swallowing the Python exception did not help: the next statement (CREATE INDEX) failed
with InFailedSQLTransactionError. Production no longer has the constraint (multi-location is in use), so the old code
would have failed there. This version never issues a statement that can fail for a missing object: it looks the
constraint up in the catalog and drops only a UNIQUE constraint on exactly (campaign_id), whatever it is named.
Composite unique constraints that merely include campaign_id are left alone.
"""
from alembic import op

revision = '020_multi_location'
down_revision = '019_motion_sensors'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("""
        DO $$
        DECLARE
            r record;
        BEGIN
            FOR r IN
                SELECT co.conname
                FROM pg_constraint co
                WHERE co.conrelid = to_regclass('location_profiles')
                  AND co.contype = 'u'
                  AND co.conkey = ARRAY[(
                      SELECT a.attnum FROM pg_attribute a
                      WHERE a.attrelid = co.conrelid AND a.attname = 'campaign_id' AND NOT a.attisdropped
                  )]
            LOOP
                EXECUTE format('ALTER TABLE location_profiles DROP CONSTRAINT %I', r.conname);
            END LOOP;
        END$$
    """)

    # Regular (non-unique) index for performance.
    op.execute("CREATE INDEX IF NOT EXISTS ix_location_profiles_campaign_id ON location_profiles (campaign_id)")


def downgrade() -> None:
    op.drop_index('ix_location_profiles_campaign_id', 'location_profiles')
    op.create_unique_constraint('location_profiles_campaign_id_key', 'location_profiles', ['campaign_id'])
