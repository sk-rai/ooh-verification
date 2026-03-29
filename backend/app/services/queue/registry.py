"""Task handler registry — maps task_type strings to async handler functions."""
from typing import Callable, Dict, Optional
import functools
import logging

logger = logging.getLogger(__name__)

_handlers: Dict[str, Callable] = {}


def task_handler(task_type: str):
    """Decorator to register an async function as a handler for a task_type."""
    def decorator(func):
        _handlers[task_type] = func
        logger.info(f"Registered task handler: {task_type}")
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def get_handler(task_type: str) -> Optional[Callable]:
    return _handlers.get(task_type)


def get_all_handlers() -> Dict[str, Callable]:
    return dict(_handlers)
