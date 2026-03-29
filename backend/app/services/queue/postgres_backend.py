"""PostgreSQL implementation of QueueBackend using SELECT ... FOR UPDATE SKIP LOCKED."""
import json
import uuid as uuid_mod
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy import select, update, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_queue import TaskQueue, TaskStatus
from app.services.queue.backend import QueueBackend


def _validate_payload(payload: Dict[str, Any]) -> None:
    """Validate that payload is JSON-serializable. Raise ValueError if not."""
    try:
        json.dumps(payload)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Task payload is not JSON-serializable: {e}")


def _serialize_uuids(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Convert UUID values in payload to strings for JSON storage."""
    result = {}
    for k, v in payload.items():
        if isinstance(v, (uuid_mod.UUID,)):
            result[k] = str(v)
        elif isinstance(v, dict):
            result[k] = _serialize_uuids(v)
        elif isinstance(v, list):
            result[k] = [str(i) if isinstance(i, uuid_mod.UUID) else i for i in v]
        else:
            result[k] = v
    return result


class PostgresQueueBackend(QueueBackend):

    async def enqueue(
        self,
        db: AsyncSession,
        task_type: str,
        payload: Dict[str, Any],
        priority: int = 0,
        scheduled_at: Optional[datetime] = None,
        max_retries: int = 3,
        tenant_id: Optional[UUID] = None,
    ) -> UUID:
        payload = _serialize_uuids(payload)
        _validate_payload(payload)

        now = datetime.now(timezone.utc)
        task = TaskQueue(
            task_type=task_type,
            payload=payload,
            status=TaskStatus.PENDING,
            priority=priority,
            scheduled_at=scheduled_at or now,
            max_retries=max_retries,
            tenant_id=tenant_id,
            created_at=now,
            updated_at=now,
        )
        db.add(task)
        await db.flush()  # Get the id without committing (caller controls transaction)
        return task.id

    async def dequeue(self, db: AsyncSession) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        # SELECT ... FOR UPDATE SKIP LOCKED — safe for concurrent workers
        stmt = (
            select(TaskQueue)
            .where(
                TaskQueue.status == TaskStatus.PENDING,
                TaskQueue.scheduled_at <= now,
            )
            .order_by(TaskQueue.priority.desc(), TaskQueue.scheduled_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            return None

        # Atomically claim the task
        task.status = TaskStatus.RUNNING
        task.started_at = now
        task.updated_at = now
        await db.commit()

        return {
            "id": task.id,
            "task_type": task.task_type,
            "payload": task.payload,
            "retry_count": task.retry_count,
            "max_retries": task.max_retries,
            "tenant_id": task.tenant_id,
        }

    async def mark_completed(self, db: AsyncSession, task_id: UUID) -> None:
        now = datetime.now(timezone.utc)
        await db.execute(
            update(TaskQueue)
            .where(TaskQueue.id == task_id)
            .values(status=TaskStatus.COMPLETED, completed_at=now, updated_at=now)
        )
        await db.commit()

    async def mark_failed(
        self,
        db: AsyncSession,
        task_id: UUID,
        error: str,
        retry_count: int,
        max_retries: int,
        base_delay: float,
        max_backoff: float,
    ) -> None:
        now = datetime.now(timezone.utc)
        new_retry_count = retry_count + 1

        if new_retry_count >= max_retries:
            # Exhausted retries — move to dead letter queue
            await db.execute(
                update(TaskQueue)
                .where(TaskQueue.id == task_id)
                .values(
                    status=TaskStatus.DEAD,
                    retry_count=new_retry_count,
                    last_error=error[:4000],
                    updated_at=now,
                )
            )
        else:
            # Reschedule with exponential backoff
            delay = min(base_delay * (2 ** retry_count), max_backoff)
            next_run = now + timedelta(seconds=delay)
            await db.execute(
                update(TaskQueue)
                .where(TaskQueue.id == task_id)
                .values(
                    status=TaskStatus.PENDING,
                    retry_count=new_retry_count,
                    last_error=error[:4000],
                    scheduled_at=next_run,
                    started_at=None,
                    updated_at=now,
                )
            )
        await db.commit()

    async def get_task_status(self, db: AsyncSession, task_id: UUID) -> Optional[str]:
        result = await db.execute(
            select(TaskQueue.status).where(TaskQueue.id == task_id)
        )
        row = result.scalar_one_or_none()
        return row.value if row else None

    async def recover_stale_tasks(self, db: AsyncSession, stale_timeout: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_timeout)
        result = await db.execute(
            select(TaskQueue)
            .where(
                TaskQueue.status == TaskStatus.RUNNING,
                TaskQueue.started_at < cutoff,
            )
            .with_for_update(skip_locked=True)
        )
        stale_tasks = result.scalars().all()
        count = 0
        now = datetime.now(timezone.utc)
        for task in stale_tasks:
            task.status = TaskStatus.PENDING
            task.retry_count += 1
            task.started_at = None
            task.last_error = "Recovered from stale running state"
            task.updated_at = now
            count += 1
        if count > 0:
            await db.commit()
        return count

    async def get_queue_depth(self, db: AsyncSession) -> Dict[str, int]:
        result = await db.execute(
            select(TaskQueue.task_type, func.count())
            .where(TaskQueue.status == TaskStatus.PENDING)
            .group_by(TaskQueue.task_type)
        )
        return {row[0]: row[1] for row in result.all()}

    async def get_dead_tasks(
        self, db: AsyncSession, task_type: Optional[str] = None,
        tenant_id: Optional[UUID] = None, limit: int = 50, offset: int = 0
    ) -> List[Dict]:
        stmt = select(TaskQueue).where(TaskQueue.status == TaskStatus.DEAD)
        if task_type:
            stmt = stmt.where(TaskQueue.task_type == task_type)
        if tenant_id:
            stmt = stmt.where(TaskQueue.tenant_id == tenant_id)
        stmt = stmt.order_by(TaskQueue.updated_at.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return [
            {
                "id": str(t.id), "task_type": t.task_type, "payload": t.payload,
                "retry_count": t.retry_count, "max_retries": t.max_retries,
                "last_error": t.last_error, "tenant_id": str(t.tenant_id) if t.tenant_id else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in result.scalars().all()
        ]

    async def retry_dead_task(self, db: AsyncSession, task_id: UUID) -> bool:
        result = await db.execute(
            select(TaskQueue).where(TaskQueue.id == task_id, TaskQueue.status == TaskStatus.DEAD)
        )
        task = result.scalar_one_or_none()
        if not task:
            return False
        now = datetime.now(timezone.utc)
        task.status = TaskStatus.PENDING
        task.retry_count = 0
        task.scheduled_at = now
        task.started_at = None
        task.completed_at = None
        task.last_error = None
        task.updated_at = now
        await db.commit()
        return True

    async def delete_dead_task(self, db: AsyncSession, task_id: UUID) -> bool:
        result = await db.execute(
            delete(TaskQueue).where(TaskQueue.id == task_id, TaskQueue.status == TaskStatus.DEAD)
        )
        await db.commit()
        return result.rowcount > 0
