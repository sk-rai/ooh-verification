"""Add vendor_client_associations table and backfill from existing data.

Supports vendor multi-client association (freelancer model).
Also adds unique constraint on vendors.phone_number.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '013_vendor_client_associations'
down_revision = '012_device_verified'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create association table
    try:
        op.create_table(
            'vendor_client_associations',
            sa.Column('association_id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('vendor_id', sa.String(6), sa.ForeignKey('vendors.vendor_id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.client_id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
            sa.Column('status', sa.Enum('active', 'inactive', name='associationstatus'), nullable=False, server_default='active'),
            sa.Column('enrolled_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('vendor_id', 'client_id', name='uq_vendor_client'),
        )
    except Exception:
        pass  # Table may already exist

    # 2. Backfill: create associations from existing created_by_client_id
    try:
        op.execute("""
            INSERT INTO vendor_client_associations (association_id, vendor_id, client_id, tenant_id, status, enrolled_at)
            SELECT gen_random_uuid(), vendor_id, created_by_client_id, tenant_id, 'active', created_at
            FROM vendors
            WHERE created_by_client_id IS NOT NULL
            ON CONFLICT (vendor_id, client_id) DO NOTHING
        """)
    except Exception:
        pass

    # 3. Add unique constraint on phone_number (skip if exists)
    try:
        op.create_index('idx_vendors_phone_unique', 'vendors', ['phone_number'], unique=True)
    except Exception:
        pass


def downgrade():
    try:
        op.drop_index('idx_vendors_phone_unique', 'vendors')
    except Exception:
        pass
    try:
        op.drop_table('vendor_client_associations')
    except Exception:
        pass
    try:
        sa.Enum(name='associationstatus').drop(op.get_bind(), checkfirst=True)
    except Exception:
        pass
