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
    # taskstatus enum and task_queue table — fully idempotent
    # Use DO block since CREATE TYPE IF NOT EXISTS requires PostgreSQL 9.1+
    # and some hosted versions don't support it via asyncpg driver
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'taskstatus') THEN
                CREATE TYPE taskstatus AS ENUM ('pending', 'running', 'completed', 'failed', 'dead');
            END IF;
        END$$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS task_queue (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_type VARCHAR(100) NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            priority INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            scheduled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3,
            last_error TEXT,
            tenant_id UUID
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_task_queue_task_type ON task_queue (task_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_task_queue_status ON task_queue (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_task_queue_tenant_id ON task_queue (tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_task_queue_poll ON task_queue (status, scheduled_at, priority)")


def downgrade() -> None:
    op.drop_table('task_queue')
    sa.Enum(name='taskstatus').drop(op.get_bind(), checkfirst=True)
