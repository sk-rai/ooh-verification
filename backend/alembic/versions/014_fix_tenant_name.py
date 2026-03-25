"""Update default tenant name to TrustCapture.

Revision ID: 014_fix_tenant_name
Revises: 013_vendor_client_associations
Create Date: 2026-03-25
"""
from alembic import op

revision = '014_fix_tenant_name'
down_revision = '013_vendor_client_associations'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE tenant_config 
        SET tenant_name = 'TrustCapture',
            email_from_name = 'TrustCapture',
            email_from_address = 'skrai382@gmail.com',
            primary_color = '#3B82F6',
            secondary_color = '#10B981'
        WHERE subdomain = 'default'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE tenant_config 
        SET tenant_name = 'Default Tenant',
            email_from_name = NULL,
            email_from_address = NULL
        WHERE subdomain = 'default'
    """)
