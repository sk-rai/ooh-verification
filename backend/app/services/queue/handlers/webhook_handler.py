"""process_webhook task handler."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.queue.registry import task_handler
from app.services.razorpay_service import get_razorpay_service
import logging

logger = logging.getLogger(__name__)


@task_handler("process_webhook")
async def handle_process_webhook(db: AsyncSession, payload: dict):
    """Process a Razorpay webhook event. Idempotent."""
    event_type = payload["event_type"]
    webhook_payload = payload["payload"]
    razorpay_svc = get_razorpay_service()
    if razorpay_svc is None:
        logger.warning("Razorpay service not configured, skipping webhook")
        return
    await razorpay_svc.handle_webhook_event(db, event_type, webhook_payload)
    logger.info(f"Processed webhook: {event_type}")
