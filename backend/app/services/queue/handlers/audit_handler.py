"""write_audit_log task handler."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.queue.registry import task_handler
from app.services.audit_logger import AuditLogger
import logging

logger = logging.getLogger(__name__)


@task_handler("write_audit_log")
async def handle_write_audit_log(db: AsyncSession, payload: dict):
    """Write an audit log entry."""
    audit_logger = AuditLogger(db)
    await audit_logger.log_photo_capture(
        photo_id=payload["photo_id"],
        vendor_id=payload["vendor_id"],
        campaign_code=payload["campaign_code"],
        sensor_data=payload.get("sensor_data", {}),
        signature=payload.get("signature", {}),
        device_info=payload.get("device_info", {}),
        flags=payload.get("flags"),
    )
    logger.info(f"Audit log written for photo {payload['photo_id']}")
