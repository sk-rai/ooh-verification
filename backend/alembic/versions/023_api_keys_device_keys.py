"""023: Bring api_keys and device_keys under Alembic control.

Both tables were historically created by CREATE TABLE IF NOT EXISTS in app/main.py startup DDL.
This migration makes them Alembic-managed. Idempotent from scratch or with the tables already present.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = '023_api_keys_device_keys'
down_revision = '022_vendor_tracks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")

    # api_keys
    op.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id UUID NOT NULL,
            tenant_id UUID NOT NULL,
            key_hash VARCHAR(255) NOT NULL,
            key_prefix VARCHAR(12) NOT NULL,
            name VARCHAR(100) NOT NULL DEFAULT 'API Key',
            permissions JSONB NOT NULL DEFAULT '["verify"]',
            rate_limit_per_minute INTEGER NOT NULL DEFAULT 60,
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_used_at TIMESTAMPTZ,
            total_calls INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_keys_prefix ON api_keys (key_prefix)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_keys_tenant ON api_keys (tenant_id)")

    # device_keys
    op.execute("""
        CREATE TABLE IF NOT EXISTS device_keys (
            key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            vendor_id VARCHAR(6) NOT NULL,
            tenant_id UUID NOT NULL,
            device_id VARCHAR(255),
            public_key TEXT NOT NULL,
            algorithm VARCHAR(50) NOT NULL DEFAULT 'ECDSA-P256',
            key_fingerprint VARCHAR(64) NOT NULL,
            active_from TIMESTAMPTZ NOT NULL DEFAULT now(),
            active_to TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_device_keys_vendor ON device_keys (vendor_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_device_keys_fingerprint ON device_keys (key_fingerprint)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_device_keys_vendor_window ON device_keys (vendor_id, active_from, active_to)")


def downgrade() -> None:
    op.drop_table('device_keys')
    op.drop_table('api_keys')
