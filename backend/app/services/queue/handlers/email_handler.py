"""send_email task handler."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.queue.registry import task_handler
from app.services.email_service import get_email_service
import logging

logger = logging.getLogger(__name__)


@task_handler("send_email")
async def handle_send_email(db: AsyncSession, payload: dict):
    """Send a templated email via SendGrid."""
    email_svc = get_email_service(db)
    await email_svc.send_templated_email(
        tenant_id=payload["tenant_id"],
        template_name=payload["template_name"],
        to_email=payload["to_email"],
        variables=payload.get("variables", {}),
    )
    logger.info(f"Sent email: {payload['template_name']} to {payload['to_email']}")
