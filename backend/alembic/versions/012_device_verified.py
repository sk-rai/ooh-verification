"""Add device_verified column to vendors table.

Supports hybrid auth: first login via OTP, subsequent logins via device attestation.
"""
from alembic import op
import sqlalchemy as sa

revision = '012_device_verified'
down_revision = '011_delivery_verification'
branch_labels = None
depends_on = None


def _add_col(table, col_name, col_type, **kwargs):
    """Safe add column — skips if already exists."""
    try:
        op.add_column(table, sa.Column(col_name, col_type, **kwargs))
    except Exception:
        pass


def upgrade():
    _add_col('vendors', 'device_verified', sa.Boolean(), server_default='false', nullable=True)


def downgrade():
    try:
        op.drop_column('vendors', 'device_verified')
    except Exception:
        pass
