"""add tenant_id to audit_logs

Revision ID: 006_add_tenant_to_audit_logs
Revises: 005_tenant_config
Create Date: 2026-03-11 11:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_add_tenant_to_audit_logs'
down_revision = '005_tenant_config'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add tenant_id column to audit_logs table."""
    # Add tenant_id column (nullable initially)
    op.add_column('audit_logs', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_audit_logs_tenant_id',
        'audit_logs',
        'tenant_config',
        ['tenant_id'],
        ['tenant_id'],
        ondelete='CASCADE'
    )
    
    # Create index for better query performance
    op.create_index('ix_audit_logs_tenant_id', 'audit_logs', ['tenant_id'])


def downgrade() -> None:
    """Remove tenant_id column from audit_logs table."""
    op.drop_index('ix_audit_logs_tenant_id', table_name='audit_logs')
    op.drop_constraint('fk_audit_logs_tenant_id', 'audit_logs', type_='foreignkey')
    op.drop_column('audit_logs', 'tenant_id')
