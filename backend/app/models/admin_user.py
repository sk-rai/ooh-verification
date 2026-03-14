"""Admin user model - platform super administrators."""
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class AdminUser(Base):
    """Super admin user - platform owner/founder only.
    Completely separate from client/vendor auth system."""

    __tablename__ = "admin_users"

    admin_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True),
                       default=lambda: datetime.now(tz=timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True),
                       default=lambda: datetime.now(tz=timezone.utc),
                       onupdate=lambda: datetime.now(tz=timezone.utc), nullable=False)

    def __repr__(self):
        return f"<AdminUser(admin_id={self.admin_id}, email={self.email})>"
