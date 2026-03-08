"""subscription enhancements for razorpay and stripe

Revision ID: 003_subscription_enhancements
Revises: 002_audit_logs
Create Date: 2026-03-07 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_subscription_enhancements'
down_revision = '002_audit_logs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new payment gateway fields
    op.add_column('subscriptions', sa.Column('payment_gateway', sa.String(length=20), nullable=True))
    op.add_column('subscriptions', sa.Column('gateway_subscription_id', sa.String(length=255), nullable=True))
    op.add_column('subscriptions', sa.Column('gateway_customer_id', sa.String(length=255), nullable=True))
    
    # Add billing details
    op.add_column('subscriptions', sa.Column('billing_cycle', sa.String(length=20), nullable=False, server_default='monthly'))
    op.add_column('subscriptions', sa.Column('amount', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('subscriptions', sa.Column('currency', sa.String(length=3), nullable=False, server_default='INR'))
    op.add_column('subscriptions', sa.Column('auto_renew', sa.Integer(), nullable=False, server_default='1'))
    
    # Add trial and cancellation dates
    op.add_column('subscriptions', sa.Column('trial_end_date', sa.DateTime(), nullable=True))
    op.add_column('subscriptions', sa.Column('cancellation_date', sa.DateTime(), nullable=True))
    
    # Add vendor and campaign quotas
    op.add_column('subscriptions', sa.Column('vendors_quota', sa.Integer(), nullable=False, server_default='2'))
    op.add_column('subscriptions', sa.Column('vendors_used', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('subscriptions', sa.Column('campaigns_quota', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('subscriptions', sa.Column('campaigns_used', sa.Integer(), nullable=False, server_default='0'))
    
    # Add storage quotas
    op.add_column('subscriptions', sa.Column('storage_quota_mb', sa.Integer(), nullable=False, server_default='500'))
    op.add_column('subscriptions', sa.Column('storage_used_mb', sa.Integer(), nullable=False, server_default='0'))
    
    # Create unique index on gateway_subscription_id
    op.create_index(op.f('ix_subscriptions_gateway_subscription_id'), 'subscriptions', ['gateway_subscription_id'], unique=True)
    
    # Update existing subscriptions with default quotas based on tier
    # Free: 50 photos, 2 vendors, 1 campaign, 500 MB
    # Pro: 1000 photos, 10 vendors, 5 campaigns, 10 GB (10240 MB)
    # Enterprise: unlimited (set high values)
    op.execute("""
        UPDATE subscriptions 
        SET vendors_quota = CASE 
            WHEN tier = 'free' THEN 2
            WHEN tier = 'pro' THEN 10
            WHEN tier = 'enterprise' THEN 999999
        END,
        campaigns_quota = CASE 
            WHEN tier = 'free' THEN 1
            WHEN tier = 'pro' THEN 5
            WHEN tier = 'enterprise' THEN 999999
        END,
        storage_quota_mb = CASE 
            WHEN tier = 'free' THEN 500
            WHEN tier = 'pro' THEN 10240
            WHEN tier = 'enterprise' THEN 102400
        END
        WHERE tier IN ('free', 'pro', 'enterprise')
    """)


def downgrade() -> None:
    # Drop index
    op.drop_index(op.f('ix_subscriptions_gateway_subscription_id'), table_name='subscriptions')
    
    # Drop storage columns
    op.drop_column('subscriptions', 'storage_used_mb')
    op.drop_column('subscriptions', 'storage_quota_mb')
    
    # Drop vendor and campaign columns
    op.drop_column('subscriptions', 'campaigns_used')
    op.drop_column('subscriptions', 'campaigns_quota')
    op.drop_column('subscriptions', 'vendors_used')
    op.drop_column('subscriptions', 'vendors_quota')
    
    # Drop trial and cancellation dates
    op.drop_column('subscriptions', 'cancellation_date')
    op.drop_column('subscriptions', 'trial_end_date')
    
    # Drop billing details
    op.drop_column('subscriptions', 'auto_renew')
    op.drop_column('subscriptions', 'currency')
    op.drop_column('subscriptions', 'amount')
    op.drop_column('subscriptions', 'billing_cycle')
    
    # Drop payment gateway fields
    op.drop_column('subscriptions', 'gateway_customer_id')
    op.drop_column('subscriptions', 'gateway_subscription_id')
    op.drop_column('subscriptions', 'payment_gateway')
