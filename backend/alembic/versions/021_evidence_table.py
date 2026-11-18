"""021: Create evidence, gps_tracks, and cases tables.

Unified evidence model supporting photo, video, voice note, and text note captures.
Campaign-optional for quick capture / event-driven evidence.

M1 repair (migration-drift): the startup DDL in app/main.py already creates these tables in production, so the plain
CREATE TABLE failed with DuplicateTableError. Every statement is now idempotent and the definitions are unchanged from the
original migration. Indexes the original migration defined but production never received (the startup DDL omits them) are
created here: ix_cases_tenant_id, ix_cases_client_id, ix_evidence_evidence_id, ix_evidence_category,
ix_evidence_tenant_type, ix_evidence_campaign_vendor.

Not in scope here (tracked for M2): evidence.signing_key_id / signing_key_fingerprint / signature_outcome, the
device_keys / api_keys / vendor_tracks tables and the geofence columns are still created only by the startup DDL.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = '021_evidence'
down_revision = '020_multi_location'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")

    # Cases table (for grouping related evidence)
    op.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            category VARCHAR(50),
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_cases_tenant_id ON cases (tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cases_client_id ON cases (client_id)")

    # Evidence table (unified captures)
    op.execute("""
        CREATE TABLE IF NOT EXISTS evidence (
            evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            campaign_id UUID REFERENCES campaigns(campaign_id) ON DELETE SET NULL,
            vendor_id VARCHAR(6) NOT NULL REFERENCES vendors(vendor_id) ON DELETE CASCADE,
            case_id UUID REFERENCES cases(case_id) ON DELETE SET NULL,
            evidence_type VARCHAR(20) NOT NULL,
            category VARCHAR(50),
            file_key VARCHAR(500),
            file_url VARCHAR(500),
            thumbnail_key VARCHAR(500),
            thumbnail_url VARCHAR(500),
            file_size_bytes BIGINT,
            mime_type VARCHAR(50),
            duration_seconds FLOAT,
            text_content TEXT,
            capture_timestamp TIMESTAMPTZ,
            latitude FLOAT,
            longitude FLOAT,
            accuracy FLOAT,
            verification_status VARCHAR(20) NOT NULL DEFAULT 'pending',
            verification_confidence FLOAT,
            verification_flags JSONB DEFAULT '[]',
            device_signature TEXT,
            file_hash VARCHAR(128),
            sensor_data JSONB,
            tags JSONB DEFAULT '[]',
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    for name, cols in (
        ('ix_evidence_evidence_id', 'evidence_id'),
        ('ix_evidence_tenant_id', 'tenant_id'),
        ('ix_evidence_campaign_id', 'campaign_id'),
        ('ix_evidence_vendor_id', 'vendor_id'),
        ('ix_evidence_type', 'evidence_type'),
        ('ix_evidence_category', 'category'),
        ('ix_evidence_status', 'verification_status'),
        ('ix_evidence_tenant_type', 'tenant_id, evidence_type'),
        ('ix_evidence_campaign_vendor', 'campaign_id, vendor_id'),
        ('ix_evidence_created', 'created_at'),
    ):
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON evidence ({cols})")

    # GPS Tracks table (for video continuous location recording)
    op.execute("""
        CREATE TABLE IF NOT EXISTS gps_tracks (
            track_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            evidence_id UUID NOT NULL REFERENCES evidence(evidence_id) ON DELETE CASCADE UNIQUE,
            points JSONB NOT NULL,
            duration_seconds FLOAT,
            total_distance_meters FLOAT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_gps_tracks_evidence_id ON gps_tracks (evidence_id)")

    # Add asset_id and location_description to location_profiles (for coordinate-only locations)
    op.execute("ALTER TABLE location_profiles ADD COLUMN IF NOT EXISTS asset_id VARCHAR(100)")
    op.execute("ALTER TABLE location_profiles ADD COLUMN IF NOT EXISTS asset_type VARCHAR(50)")
    op.execute("ALTER TABLE location_profiles ADD COLUMN IF NOT EXISTS location_description TEXT")


def downgrade() -> None:
    # WARNING: destroys evidence data. Never run against production.
    op.drop_column('location_profiles', 'location_description')
    op.drop_column('location_profiles', 'asset_type')
    op.drop_column('location_profiles', 'asset_id')
    op.drop_table('gps_tracks')
    op.drop_table('evidence')
    op.drop_table('cases')
