"""Task queue public API."""
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.queue.config import queue_config
from app.services.queue.backend import QueueBackend

_backend = None


def get_queue_backend() -> QueueBackend:
    global _backend
    if _backend is None:
        if queue_config.TASK_QUEUE_BACKEND == "postgresql":
            from app.services.queue.postgres_backend import PostgresQueueBackend
            _backend = PostgresQueueBackend()
        else:
            raise ValueError(f"Unknown queue backend: {queue_config.TASK_QUEUE_BACKEND}")
    return _backend


async def enqueue(
    db: AsyncSession,
    task_type: str,
    payload: Dict[str, Any],
    priority: int = 0,
    scheduled_at: Optional[datetime] = None,
    max_retries: int = 3,
    tenant_id: Optional[UUID] = None,
) -> UUID:
    """Public API to enqueue a task. Participates in the caller's DB transaction."""
    backend = get_queue_backend()
    return await backend.enqueue(
        db, task_type, payload, priority, scheduled_at, max_retries, tenant_id
    )
