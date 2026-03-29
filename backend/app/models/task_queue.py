"""
Task Queue model for background job processing.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, Text, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"


class TaskQueue(Base):
    __tablename__ = "task_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(String(100), nullable=False, index=True)
    payload = Column(JSONB, nullable=False, default=dict)
    status = Column(
        SQLEnum(TaskStatus, name="taskstatus", native_enum=True,
                values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=TaskStatus.PENDING, index=True
    )
    priority = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Retry metadata
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    last_error = Column(Text, nullable=True)

    # Multi-tenancy
    tenant_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    __table_args__ = (
        Index("ix_task_queue_poll", "status", "scheduled_at", "priority"),
    )
