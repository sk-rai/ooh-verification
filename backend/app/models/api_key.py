"""
API Key model for 3rd party authentication.
Stateless verification-as-a-service credentials.
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

from app.core.database import Base


class APIKey(Base):
    """API key for server-to-server authentication."""
    __tablename__ = "api_keys"

    key_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    client_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Key storage (hash only, never store raw key)
    key_hash = Column(String(255), nullable=False)
    key_prefix = Column(String(12), nullable=False, index=True)  # "tc_live_a1b2" for lookup

    # Metadata
    name = Column(String(100), nullable=False)  # "Production Key"
    permissions = Column(JSONB, nullable=False, default=lambda: ["verify"])
    rate_limit_per_minute = Column(Integer, nullable=False, default=60)
    is_active = Column(Boolean, nullable=False, default=True)

    # Usage tracking
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    total_calls = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)

    def __repr__(self):
        return f"<APIKey(prefix={self.key_prefix}, name={self.name}, active={self.is_active})>"
