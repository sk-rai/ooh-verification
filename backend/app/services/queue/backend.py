"""Abstract queue backend interface."""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession


class QueueBackend(ABC):
    @abstractmethod
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
        """Insert a task. Returns the task UUID."""
        ...

    @abstractmethod
    async def dequeue(self, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """Claim the next pending task using FOR UPDATE SKIP LOCKED."""
        ...

    @abstractmethod
    async def mark_completed(self, db: AsyncSession, task_id: UUID) -> None:
        """Set task status to completed."""
        ...

    @abstractmethod
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
        """Handle task failure with retry or dead letter."""
        ...

    @abstractmethod
    async def get_task_status(self, db: AsyncSession, task_id: UUID) -> Optional[str]:
        """Return the current status string for a task."""
        ...

    @abstractmethod
    async def recover_stale_tasks(self, db: AsyncSession, stale_timeout: int) -> int:
        """Reset stale running tasks to pending. Returns count recovered."""
        ...

    @abstractmethod
    async def get_queue_depth(self, db: AsyncSession) -> Dict[str, int]:
        """Return {task_type: count} for pending tasks."""
        ...

    @abstractmethod
    async def get_dead_tasks(self, db: AsyncSession, task_type: Optional[str] = None,
                             tenant_id: Optional[UUID] = None, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Return list of dead tasks."""
        ...

    @abstractmethod
    async def retry_dead_task(self, db: AsyncSession, task_id: UUID) -> bool:
        """Reset a dead task to pending."""
        ...

    @abstractmethod
    async def delete_dead_task(self, db: AsyncSession, task_id: UUID) -> bool:
        """Permanently delete a dead task."""
        ...
