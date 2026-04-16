"""Add motion sensor columns (accelerometer, gyroscope, orientation) for schema v2.1.

Revision ID: 019_motion_sensors
Revises: 018_task_queue
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '019_motion_sensors'
down_revision = '018_task_queue'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sensor_data', sa.Column('accelerometer_data', JSONB, nullable=True))
    op.add_column('sensor_data', sa.Column('gyroscope_data', JSONB, nullable=True))
    op.add_column('sensor_data', sa.Column('orientation_data', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('sensor_data', 'orientation_data')
    op.drop_column('sensor_data', 'gyroscope_data')
    op.drop_column('sensor_data', 'accelerometer_data')
