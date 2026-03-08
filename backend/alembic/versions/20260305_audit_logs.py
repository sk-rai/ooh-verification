"""Add audit_logs table with immutability triggers

Revision ID: 002_audit_logs
Revises: 001_initial
Create Date: 2026-03-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_audit_logs'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create audit_logs table with immutability enforcement."""
    
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('audit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('vendor_id', sa.String(length=6), nullable=False),
        sa.Column('photo_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('campaign_code', sa.String(length=50), nullable=False),
        sa.Column('sensor_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('signature', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('device_info', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('previous_record_hash', sa.String(length=64), nullable=True),
        sa.Column('record_hash', sa.String(length=64), nullable=False),
        sa.Column('audit_flags', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('audit_id')
    )
    
    # Create indexes for efficient querying
    op.create_index('idx_audit_logs_vendor_id', 'audit_logs', ['vendor_id'])
    op.create_index('idx_audit_logs_photo_id', 'audit_logs', ['photo_id'])
    op.create_index('idx_audit_logs_campaign_code', 'audit_logs', ['campaign_code'])
    op.create_index('idx_audit_logs_vendor_timestamp', 'audit_logs', ['vendor_id', sa.text('timestamp DESC')])
    op.create_index('idx_audit_logs_campaign_timestamp', 'audit_logs', ['campaign_code', sa.text('timestamp DESC')])
    
    # Create function to prevent modifications
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Audit logs are immutable and cannot be modified or deleted';
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger to prevent updates
    op.execute("""
        CREATE TRIGGER audit_log_immutable_update
            BEFORE UPDATE ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_log_modification();
    """)
    
    # Create trigger to prevent deletes
    op.execute("""
        CREATE TRIGGER audit_log_immutable_delete
            BEFORE DELETE ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_log_modification();
    """)


def downgrade() -> None:
    """Remove audit_logs table and triggers."""
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS audit_log_immutable_delete ON audit_logs")
    op.execute("DROP TRIGGER IF EXISTS audit_log_immutable_update ON audit_logs")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification()")
    
    # Drop indexes
    op.drop_index('idx_audit_logs_campaign_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_logs_vendor_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_logs_campaign_code', table_name='audit_logs')
    op.drop_index('idx_audit_logs_photo_id', table_name='audit_logs')
    op.drop_index('idx_audit_logs_vendor_id', table_name='audit_logs')
    
    # Drop table
    op.drop_table('audit_logs')
