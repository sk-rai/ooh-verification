"""Add task_queue table for background job processing.

Revision ID: 018_task_queue
Revises: 017_visitor_analytics
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision = '018_task_queue'
down_revision = '017_visitor_analytics'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create TaskStatus enum
    task_status_enum = sa.Enum(
        'pending', 'running', 'completed', 'failed', 'dead',
        name='taskstatus'
    )
    task_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table('task_queue',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('task_type', sa.String(100), nullable=False),
        sa.Column('payload', JSONB, nullable=False, server_default='{}'),
        sa.Column('status', task_status_enum, nullable=False, server_default='pending'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=True),
    )

    # Indexes for efficient polling and filtering
    op.create_index('ix_task_queue_task_type', 'task_queue', ['task_type'])
    op.create_index('ix_task_queue_status', 'task_queue', ['status'])
    op.create_index('ix_task_queue_tenant_id', 'task_queue', ['tenant_id'])
    op.create_index('ix_task_queue_poll', 'task_queue', ['status', 'scheduled_at', 'priority'])


def downgrade() -> None:
    op.drop_table('task_queue')
    sa.Enum(name='taskstatus').drop(op.get_bind(), checkfirst=True)
