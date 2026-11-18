"""Add motion sensor columns (accelerometer, gyroscope, orientation) for schema v2.1.

Revision ID: 019_motion_sensors
Revises: 018_task_queue
Create Date: 2026-04-04

M1 repair (migration-drift): the startup DDL in app/main.py has been adding these columns on every boot, so production
already has them and the plain ADD COLUMN failed with DuplicateColumnError, rolling back the whole upgrade (production
has been stuck at revision 017). ADD COLUMN IF NOT EXISTS converges from any starting state.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '019_motion_sensors'
down_revision = '018_task_queue'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS accelerometer_data JSONB")
    op.execute("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS gyroscope_data JSONB")
    op.execute("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS orientation_data JSONB")


def downgrade() -> None:
    op.drop_column('sensor_data', 'orientation_data')
    op.drop_column('sensor_data', 'gyroscope_data')
    op.drop_column('sensor_data', 'accelerometer_data')
