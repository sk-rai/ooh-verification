"""Queue configuration from environment variables."""
import os


class QueueConfig:
    TASK_QUEUE_BACKEND: str = os.getenv("TASK_QUEUE_BACKEND", "postgresql")
    TASK_QUEUE_POLLING_INTERVAL: int = int(os.getenv("TASK_QUEUE_POLLING_INTERVAL", "5"))
    TASK_QUEUE_BASE_DELAY: int = int(os.getenv("TASK_QUEUE_BASE_DELAY", "30"))
    TASK_QUEUE_MAX_BACKOFF: int = int(os.getenv("TASK_QUEUE_MAX_BACKOFF", "3600"))
    TASK_QUEUE_STALE_TIMEOUT: int = int(os.getenv("TASK_QUEUE_STALE_TIMEOUT", "600"))
    TASK_QUEUE_STALE_CHECK_INTERVAL: int = int(os.getenv("TASK_QUEUE_STALE_CHECK_INTERVAL", "60"))
    TASK_QUEUE_MAX_DEPTH_WARNING: int = int(os.getenv("TASK_QUEUE_MAX_DEPTH_WARNING", "100"))
    TASK_QUEUE_WORKER_MODE: str = os.getenv("TASK_QUEUE_WORKER_MODE", "in-process")


queue_config = QueueConfig()
