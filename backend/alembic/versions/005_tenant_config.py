"""add tenant_config table for multi-tenancy

Revision ID: 005_tenant_config
Revises: 004_campaign_locations
Create Date: 2026-03-10 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = '005_tenant_config'
down_revision = '004_campaign_locations'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tenant_config table
    op.create_table(
        'tenant_config',
        sa.Column('tenant_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_name', sa.String(length=255), nullable=False),
        sa.Column('subdomain', sa.String(length=100), nullable=True),
        sa.Column('custom_domain', sa.String(length=255), nullable=True),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('primary_color', sa.String(length=7), nullable=True, server_default='#3B82F6'),  # Default blue
        sa.Column('secondary_color', sa.String(length=7), nullable=True, server_default='#10B981'),  # Default green
        sa.Column('email_from_name', sa.String(length=255), nullable=True),
        sa.Column('email_from_address', sa.String(length=255), nullable=True),
        sa.Column('email_templates', JSONB, nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()'))
    )

    # Create unique constraints
    op.create_unique_constraint('uq_tenant_subdomain', 'tenant_config', ['subdomain'])
    op.create_unique_constraint('uq_tenant_custom_domain', 'tenant_config', ['custom_domain'])

    # Create indexes
    op.create_index('idx_tenant_subdomain', 'tenant_config', ['subdomain'])
    op.create_index('idx_tenant_custom_domain', 'tenant_config', ['custom_domain'])
    op.create_index('idx_tenant_is_active', 'tenant_config', ['is_active'])

    # Create default tenant for existing data
    op.execute("""
        INSERT INTO tenant_config (tenant_name, subdomain, is_active, created_at, updated_at)
        VALUES ('Default Tenant', 'default', true, NOW(), NOW())
    """)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_tenant_is_active', table_name='tenant_config')
    op.drop_index('idx_tenant_custom_domain', table_name='tenant_config')
    op.drop_index('idx_tenant_subdomain', table_name='tenant_config')

    # Drop unique constraints
    op.drop_constraint('uq_tenant_custom_domain', 'tenant_config', type_='unique')
    op.drop_constraint('uq_tenant_subdomain', 'tenant_config', type_='unique')

    # Drop table
    op.drop_table('tenant_config')
