"""Add GST and refund fields to subscriptions.

Revision ID: 016_gst_and_refunds
Revises: 015_profile_fields
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = '016_gst_and_refunds'
down_revision = '015_profile_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # GST fields
    op.add_column('subscriptions', sa.Column('base_amount', sa.Integer(), nullable=True))
    op.add_column('subscriptions', sa.Column('gst_rate', sa.Integer(), nullable=True, server_default='18'))
    op.add_column('subscriptions', sa.Column('gst_amount', sa.Integer(), nullable=True))
    op.add_column('subscriptions', sa.Column('total_amount', sa.Integer(), nullable=True))
    op.add_column('subscriptions', sa.Column('customer_gstin', sa.String(20), nullable=True))
    op.add_column('subscriptions', sa.Column('customer_state', sa.String(100), nullable=True))

    # Refund fields
    op.add_column('subscriptions', sa.Column('refund_amount', sa.Integer(), nullable=True))
    op.add_column('subscriptions', sa.Column('refund_status', sa.String(20), nullable=True))
    op.add_column('subscriptions', sa.Column('refund_id', sa.String(255), nullable=True))
    op.add_column('subscriptions', sa.Column('refund_initiated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('cancelled_reason', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('subscriptions', 'base_amount')
    op.drop_column('subscriptions', 'gst_rate')
    op.drop_column('subscriptions', 'gst_amount')
    op.drop_column('subscriptions', 'total_amount')
    op.drop_column('subscriptions', 'customer_gstin')
    op.drop_column('subscriptions', 'customer_state')
    op.drop_column('subscriptions', 'refund_amount')
    op.drop_column('subscriptions', 'refund_status')
    op.drop_column('subscriptions', 'refund_id')
    op.drop_column('subscriptions', 'refund_initiated_at')
    op.drop_column('subscriptions', 'cancelled_reason')
