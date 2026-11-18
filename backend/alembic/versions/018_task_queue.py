"""Add task_queue table for background job processing.

Revision ID: 018_task_queue
Revises: 017_visitor_analytics
Create Date: 2026-03-30

M1 repair (migration-drift): every statement is idempotent and the column types match the model and the startup DDL
in app/main.py. Production already has this table (created by the startup DDL), so on production this migration only
verifies; on a fresh database it now creates the same shape the application expects.
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
    # Never queue behind a long-running transaction while the API is serving traffic: fail fast and roll back the
    # whole upgrade instead (start.sh tolerates a failed migration; the next deploy retries). SET LOCAL ends with the
    # transaction Alembic runs the upgrade in.
    op.execute("SET LOCAL lock_timeout = '5s'")

    # taskstatus enum — DO block because CREATE TYPE has no IF NOT EXISTS.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'taskstatus') THEN
                CREATE TYPE taskstatus AS ENUM ('pending', 'running', 'completed', 'failed', 'dead');
            END IF;
        END$$
    """)

    # status is the native enum, exactly as the TaskQueue model and the startup DDL define it. (It used to be TEXT
    # here, which made dequeue fail with "operator does not exist: text = taskstatus" on a database built from
    # migrations alone.)
    op.execute("""
        CREATE TABLE IF NOT EXISTS task_queue (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_type VARCHAR(100) NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}',
            status taskstatus NOT NULL DEFAULT 'pending',
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
