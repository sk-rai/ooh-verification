"""021: Create evidence, gps_tracks, and cases tables.

Unified evidence model supporting photo, video, voice note, and text note captures.
Campaign-optional for quick capture / event-driven evidence.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = '021_evidence'
down_revision = '020_multi_location'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cases table (for grouping related evidence)
    op.create_table(
        'cases',
        sa.Column('case_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('client_id', UUID(as_uuid=True), sa.ForeignKey('clients.client_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Evidence table (unified captures)
    op.create_table(
        'evidence',
        sa.Column('evidence_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('campaign_id', UUID(as_uuid=True), sa.ForeignKey('campaigns.campaign_id', ondelete='SET NULL'), nullable=True),
        sa.Column('vendor_id', sa.String(6), sa.ForeignKey('vendors.vendor_id', ondelete='CASCADE'), nullable=False),
        sa.Column('case_id', UUID(as_uuid=True), sa.ForeignKey('cases.case_id', ondelete='SET NULL'), nullable=True),
        sa.Column('evidence_type', sa.String(20), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('file_key', sa.String(500), nullable=True),
        sa.Column('file_url', sa.String(500), nullable=True),
        sa.Column('thumbnail_key', sa.String(500), nullable=True),
        sa.Column('thumbnail_url', sa.String(500), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger, nullable=True),
        sa.Column('mime_type', sa.String(50), nullable=True),
        sa.Column('duration_seconds', sa.Float, nullable=True),
        sa.Column('text_content', sa.Text, nullable=True),
        sa.Column('capture_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('latitude', sa.Float, nullable=True),
        sa.Column('longitude', sa.Float, nullable=True),
        sa.Column('accuracy', sa.Float, nullable=True),
        sa.Column('verification_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('verification_confidence', sa.Float, nullable=True),
        sa.Column('verification_flags', JSONB, nullable=True, server_default='[]'),
        sa.Column('device_signature', sa.Text, nullable=True),
        sa.Column('file_hash', sa.String(128), nullable=True),
        sa.Column('sensor_data', JSONB, nullable=True),
        sa.Column('tags', JSONB, nullable=True, server_default='[]'),
        sa.Column('metadata', JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_evidence_evidence_id', 'evidence', ['evidence_id'])
    op.create_index('ix_evidence_tenant_id', 'evidence', ['tenant_id'])
    op.create_index('ix_evidence_campaign_id', 'evidence', ['campaign_id'])
    op.create_index('ix_evidence_vendor_id', 'evidence', ['vendor_id'])
    op.create_index('ix_evidence_type', 'evidence', ['evidence_type'])
    op.create_index('ix_evidence_category', 'evidence', ['category'])
    op.create_index('ix_evidence_status', 'evidence', ['verification_status'])
    op.create_index('ix_evidence_tenant_type', 'evidence', ['tenant_id', 'evidence_type'])
    op.create_index('ix_evidence_campaign_vendor', 'evidence', ['campaign_id', 'vendor_id'])
    op.create_index('ix_evidence_created', 'evidence', ['created_at'])

    # GPS Tracks table (for video continuous location recording)
    op.create_table(
        'gps_tracks',
        sa.Column('track_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('evidence_id', UUID(as_uuid=True), sa.ForeignKey('evidence.evidence_id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('points', JSONB, nullable=False),
        sa.Column('duration_seconds', sa.Float, nullable=True),
        sa.Column('total_distance_meters', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_gps_tracks_evidence_id', 'gps_tracks', ['evidence_id'])

    # Add asset_id and location_description to location_profiles (for coordinate-only locations)
    op.add_column('location_profiles', sa.Column('asset_id', sa.String(100), nullable=True))
    op.add_column('location_profiles', sa.Column('asset_type', sa.String(50), nullable=True))
    op.add_column('location_profiles', sa.Column('location_description', sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column('location_profiles', 'location_description')
    op.drop_column('location_profiles', 'asset_type')
    op.drop_column('location_profiles', 'asset_id')
    op.drop_table('gps_tracks')
    op.drop_table('evidence')
    op.drop_table('cases')
