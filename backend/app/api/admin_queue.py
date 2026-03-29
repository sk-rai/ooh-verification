"""Admin API endpoints for task queue monitoring and DLQ management."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.services.queue import get_queue_backend

router = APIRouter(prefix="/api/admin/queue", tags=["admin-queue"])


@router.get("/depth")
async def get_queue_depth(db: AsyncSession = Depends(get_db)):
    """Return {task_type: count} for pending tasks."""
    backend = get_queue_backend()
    depth = await backend.get_queue_depth(db)
    return {"pending": depth, "total": sum(depth.values())}


@router.get("/dead")
async def get_dead_count(db: AsyncSession = Depends(get_db)):
    """Return count of dead tasks by type."""
    from sqlalchemy import select, func
    from app.models.task_queue import TaskQueue, TaskStatus
    result = await db.execute(
        select(TaskQueue.task_type, func.count())
        .where(TaskQueue.status == TaskStatus.DEAD)
        .group_by(TaskQueue.task_type)
    )
    counts = {row[0]: row[1] for row in result.all()}
    return {"dead": counts, "total": sum(counts.values())}


@router.get("/dead/list")
async def list_dead_tasks(
    task_type: Optional[str] = None,
    tenant_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of dead tasks."""
    backend = get_queue_backend()
    tid = UUID(tenant_id) if tenant_id else None
    tasks = await backend.get_dead_tasks(db, task_type=task_type, tenant_id=tid, limit=limit, offset=offset)
    return {"tasks": tasks, "count": len(tasks)}


@router.post("/dead/{task_id}/retry")
async def retry_dead_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Reset a dead task to pending for retry."""
    backend = get_queue_backend()
    success = await backend.retry_dead_task(db, UUID(task_id))
    if not success:
        raise HTTPException(status_code=404, detail="Dead task not found")
    return {"status": "retried", "task_id": task_id}


@router.delete("/dead/{task_id}")
async def delete_dead_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Permanently delete a dead task."""
    backend = get_queue_backend()
    success = await backend.delete_dead_task(db, UUID(task_id))
    if not success:
        raise HTTPException(status_code=404, detail="Dead task not found")
    return {"status": "deleted", "task_id": task_id}
