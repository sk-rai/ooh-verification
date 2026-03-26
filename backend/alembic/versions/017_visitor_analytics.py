"""Add visitor analytics tables.

Revision ID: 017_visitor_analytics
Revises: 016_gst_and_refunds
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '017_visitor_analytics'
down_revision = '016_gst_and_refunds'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Raw page views (kept for 30 days, then purged)
    op.create_table('page_views',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('visitor_hash', sa.String(64), nullable=False, index=True),
        sa.Column('session_id', sa.String(64), nullable=True),
        sa.Column('page', sa.String(500), nullable=False),
        sa.Column('referrer', sa.String(1000), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('device_type', sa.String(20), nullable=True),
        sa.Column('browser', sa.String(50), nullable=True),
        sa.Column('os', sa.String(50), nullable=True),
        sa.Column('utm_source', sa.String(200), nullable=True),
        sa.Column('utm_medium', sa.String(200), nullable=True),
        sa.Column('utm_campaign', sa.String(200), nullable=True),
        sa.Column('is_registered_user', sa.Boolean(), default=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )

    # Daily summaries (kept forever)
    op.create_table('daily_analytics_summary',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('date', sa.Date(), nullable=False, index=True),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=True),
        sa.Column('total_views', sa.Integer(), default=0),
        sa.Column('unique_visitors', sa.Integer(), default=0),
        sa.Column('unique_sessions', sa.Integer(), default=0),
        sa.Column('registered_views', sa.Integer(), default=0),
        sa.Column('top_pages', sa.JSON(), nullable=True),
        sa.Column('top_referrers', sa.JSON(), nullable=True),
        sa.Column('countries', sa.JSON(), nullable=True),
        sa.Column('devices', sa.JSON(), nullable=True),
        sa.Column('browsers', sa.JSON(), nullable=True),
        sa.Column('utm_sources', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('date', 'tenant_id', name='uq_daily_summary_date_tenant'),
    )


def downgrade() -> None:
    op.drop_table('daily_analytics_summary')
    op.drop_table('page_views')
