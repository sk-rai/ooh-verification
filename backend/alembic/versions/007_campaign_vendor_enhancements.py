"""Add location fields and timestamps to campaign_vendor_assignments

Revision ID: 007_campaign_vendor_enhancements
Revises: 006_add_tenant_to_audit_logs
Create Date: 2026-03-13 12:00:00.000000

Changes:
- Add location fields to campaign_vendor_assignments (address, lat/lon, name)
- Add created_at and updated_at to campaign_vendor_assignments
- Add updated_at to location_profiles (can be updated)
- Photos, photo_signatures, sensor_data remain immutable (no updated_at)

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007_campaign_vendor_enhancements'
down_revision = '006_add_tenant_to_audit_logs'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add location fields and timestamps to campaign_vendor_assignments.
    Add updated_at to location_profiles only (photos are immutable).
    """
    
    # 1. Add location fields to campaign_vendor_assignments
    op.add_column('campaign_vendor_assignments',
                  sa.Column('assignment_address', sa.String(500), nullable=True))
    op.add_column('campaign_vendor_assignments',
                  sa.Column('assignment_latitude', sa.Float, nullable=True))
    op.add_column('campaign_vendor_assignments',
                  sa.Column('assignment_longitude', sa.Float, nullable=True))
    op.add_column('campaign_vendor_assignments',
                  sa.Column('assignment_location_name', sa.String(255), nullable=True))
    
    # 2. Add created_at and updated_at to campaign_vendor_assignments
    # Note: assigned_at already exists, we'll keep it for backward compatibility
    op.add_column('campaign_vendor_assignments',
                  sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('campaign_vendor_assignments',
                  sa.Column('updated_at', sa.DateTime(), nullable=True))
    
    # Set created_at to assigned_at for existing records
    op.execute("""
        UPDATE campaign_vendor_assignments 
        SET created_at = assigned_at, updated_at = assigned_at 
        WHERE created_at IS NULL
    """)
    
    # Make created_at and updated_at non-nullable after backfilling
    op.alter_column('campaign_vendor_assignments', 'created_at', nullable=False)
    op.alter_column('campaign_vendor_assignments', 'updated_at', nullable=False)
    
    # 3. Add check constraint for location data
    # Either address OR (latitude AND longitude) must be provided if location is specified
    op.create_check_constraint(
        'check_location_data',
        'campaign_vendor_assignments',
        '(assignment_address IS NULL AND assignment_latitude IS NULL AND assignment_longitude IS NULL) OR '
        '(assignment_address IS NOT NULL) OR '
        '(assignment_latitude IS NOT NULL AND assignment_longitude IS NOT NULL)'
    )
    
    # 4. Add updated_at to location_profiles (these can be updated)
    op.add_column('location_profiles',
                  sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.execute("""
        UPDATE location_profiles 
        SET updated_at = created_at 
        WHERE updated_at IS NULL
    """)
    op.alter_column('location_profiles', 'updated_at', nullable=False)
    
    # Note: photos, photo_signatures, sensor_data, and audit_logs are immutable audit records
    # They should NOT have updated_at columns to maintain data integrity and audit trail
    
    # 5. Add indexes for performance
    op.create_index('ix_campaign_vendor_assignments_created_at',
                    'campaign_vendor_assignments', ['created_at'])
    op.create_index('ix_campaign_vendor_assignments_location',
                    'campaign_vendor_assignments',
                    ['assignment_latitude', 'assignment_longitude'])


def downgrade():
    """
    Remove location fields and timestamps from campaign_vendor_assignments.
    Remove updated_at from location_profiles.
    """
    
    # Drop indexes
    op.drop_index('ix_campaign_vendor_assignments_location',
                  table_name='campaign_vendor_assignments')
    op.drop_index('ix_campaign_vendor_assignments_created_at',
                  table_name='campaign_vendor_assignments')
    
    # Drop check constraint
    op.drop_constraint('check_location_data',
                       'campaign_vendor_assignments',
                       type_='check')
    
    # Drop updated_at from location_profiles
    op.drop_column('location_profiles', 'updated_at')
    
    # Drop timestamps from campaign_vendor_assignments
    op.drop_column('campaign_vendor_assignments', 'updated_at')
    op.drop_column('campaign_vendor_assignments', 'created_at')
    
    # Drop location fields from campaign_vendor_assignments
    op.drop_column('campaign_vendor_assignments', 'assignment_location_name')
    op.drop_column('campaign_vendor_assignments', 'assignment_longitude')
    op.drop_column('campaign_vendor_assignments', 'assignment_latitude')
    op.drop_column('campaign_vendor_assignments', 'assignment_address')
