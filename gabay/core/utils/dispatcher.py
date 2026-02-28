import logging
import asyncio
from typing import Callable, Any
from gabay.worker.celery_app import celery_app
from gabay.core.config import settings

logger = logging.getLogger(__name__)

async def dispatch_task(task_func: Callable, *args, **kwargs):
    """
    Dispatches a task to Celery if available, otherwise runs it in a background asyncio task.
    This ensures reliability in local development environments without workers.
    """
    user_id = args[0] if args else "unknown"
    task_name = getattr(task_func, "__name__", "unknown_task")

    # 1. Try to check for active workers
    worker_available = False
    try:
        # inspect().active() returns a dict if workers are online
        i = celery_app.control.inspect()
        active = i.active()
        if active:
            worker_available = True
    except Exception:
        # If Redis or Celery connection fails, we assume no worker
        pass

    if worker_available:
        logger.info(f"Dispatching task '{task_name}' to Celery worker for user {user_id}")
        # Assuming the task_func has a .delay attribute (is a Celery task)
        if hasattr(task_func, "delay"):
            task_func.delay(*args, **kwargs)
            return
        else:
             logger.warning(f"Task '{task_name}' is not a Celery task but worker is available. Running locally.")

    # 2. Local Fallback (Run as background asyncio task)
    logger.info(f"Running task '{task_name}' locally in background for user {user_id}")
    
    # We use a wrapper to handle potential sync/async mismatches in the background
    async def local_wrapper():
        try:
            if asyncio.iscoroutinefunction(task_func):
                await task_func(*args, **kwargs)
            else:
                # If it's a synchronous function, run it in a thread to avoid blocking loop
                await asyncio.to_thread(task_func, *args, **kwargs)
        except Exception as e:
            logger.error(f"Local background task '{task_name}' failed: {e}")

    asyncio.create_task(local_wrapper())
