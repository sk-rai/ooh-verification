"""Background task worker — polls PostgreSQL queue and executes handlers."""
import asyncio
import logging
import time
from typing import Optional

from app.core.database import AsyncSessionLocal
from app.services.queue.config import queue_config
from app.services.queue.registry import get_handler

logger = logging.getLogger(__name__)


class TaskWorker:
    def __init__(self):
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None
        self._stale_task: Optional[asyncio.Task] = None

    async def start(self):
        """Called from FastAPI startup event."""
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        self._stale_task = asyncio.create_task(self._stale_check_loop())
        logger.info(f"Task worker started (mode={queue_config.TASK_QUEUE_WORKER_MODE}, "
                     f"poll={queue_config.TASK_QUEUE_POLLING_INTERVAL}s)")

    async def stop(self):
        """Called from FastAPI shutdown event. Waits for current work to finish."""
        self._running = False
        logger.info("Task worker stopping...")
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self._stale_task:
            self._stale_task.cancel()
            try:
                await self._stale_task
            except asyncio.CancelledError:
                pass
        logger.info("Task worker stopped")

    async def _poll_loop(self):
        from app.services.queue import get_queue_backend
        backend = get_queue_backend()

        while self._running:
            try:
                async with AsyncSessionLocal() as db:
                    task = await backend.dequeue(db)
                    if task is None:
                        await asyncio.sleep(queue_config.TASK_QUEUE_POLLING_INTERVAL)
                        continue

                    task_id = task["id"]
                    task_type = task["task_type"]
                    logger.info(f"Claimed task {task_id} type={task_type}")
                    start_time = time.monotonic()

                    handler = get_handler(task_type)
                    if handler is None:
                        error_msg = f"No handler registered for task type: {task_type}"
                        logger.error(error_msg)
                        async with AsyncSessionLocal() as fail_db:
                            await backend.mark_failed(
                                fail_db, task_id, error_msg,
                                task["retry_count"], task["max_retries"],
                                queue_config.TASK_QUEUE_BASE_DELAY,
                                queue_config.TASK_QUEUE_MAX_BACKOFF,
                            )
                        continue

                    try:
                        async with AsyncSessionLocal() as handler_db:
                            await handler(handler_db, task["payload"])
                        async with AsyncSessionLocal() as complete_db:
                            await backend.mark_completed(complete_db, task_id)
                        duration = time.monotonic() - start_time
                        logger.info(f"Completed task {task_id} type={task_type} in {duration:.2f}s")
                    except Exception as e:
                        duration = time.monotonic() - start_time
                        error_msg = str(e)[:4000]
                        logger.warning(f"Task {task_id} type={task_type} failed after {duration:.2f}s: {error_msg}")
                        try:
                            async with AsyncSessionLocal() as fail_db:
                                await backend.mark_failed(
                                    fail_db, task_id, error_msg,
                                    task["retry_count"], task["max_retries"],
                                    queue_config.TASK_QUEUE_BASE_DELAY,
                                    queue_config.TASK_QUEUE_MAX_BACKOFF,
                                )
                        except Exception as mark_err:
                            logger.exception(f"Failed to mark task {task_id} as failed: {mark_err}")

                    # Check queue depth warning
                    try:
                        async with AsyncSessionLocal() as depth_db:
                            depth = await backend.get_queue_depth(depth_db)
                            total = sum(depth.values())
                            if total > queue_config.TASK_QUEUE_MAX_DEPTH_WARNING:
                                logger.warning(f"Queue depth warning: {total} pending tasks {depth}")
                    except Exception:
                        pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Worker poll error: {e}")
                await asyncio.sleep(queue_config.TASK_QUEUE_POLLING_INTERVAL)

    async def _stale_check_loop(self):
        from app.services.queue import get_queue_backend
        backend = get_queue_backend()

        while self._running:
            try:
                await asyncio.sleep(queue_config.TASK_QUEUE_STALE_CHECK_INTERVAL)
                async with AsyncSessionLocal() as db:
                    count = await backend.recover_stale_tasks(db, queue_config.TASK_QUEUE_STALE_TIMEOUT)
                    if count > 0:
                        logger.warning(f"Recovered {count} stale tasks")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Stale check error: {e}")


# Singleton
task_worker = TaskWorker()
