"""
DeviceKey model — append-only history of vendor device public keys.

A vendor's signing key can be regenerated on the device (reinstall, clear-data,
restore/migration, Keystore eviction). Previously the backend overwrote the single
`vendors.public_key`, orphaning all evidence signed under the prior key. This table
retains every registered key with an [active_from, active_to) validity window so
historical evidence stays verifiable against the key that was active when it was
signed.

See web/demo-shots/KEY_VERSIONING_DESIGN.md.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.core.database import Base


class DeviceKey(Base):
    """One registered device public key for a vendor, with a validity window."""
    __tablename__ = "device_keys"

    key_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    vendor_id = Column(String(6), ForeignKey("vendors.vendor_id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    device_id = Column(String(255), nullable=True)

    public_key = Column(String, nullable=False)              # PEM
    algorithm = Column(String(50), nullable=False, default="ECDSA-P256")
    key_fingerprint = Column(String(64), nullable=False, index=True)  # SHA-256 of normalized PEM

    # Validity window. active_to IS NULL => current active key.
    active_from = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(tz=__import__("datetime").timezone.utc))
    active_to = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(tz=__import__("datetime").timezone.utc))

    __table_args__ = (
        Index("ix_device_keys_vendor_window", "vendor_id", "active_from", "active_to"),
    )

    def __repr__(self):
        state = "active" if self.active_to is None else "retired"
        return f"<DeviceKey(vendor={self.vendor_id}, fp={self.key_fingerprint[:12]}…, {state})>"
