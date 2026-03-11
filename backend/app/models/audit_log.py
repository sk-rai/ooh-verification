"""
Audit Log model - immutable audit trail for photo captures.
"""
from sqlalchemy import Column, String, DateTime, ARRAY, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

from app.core.database import Base


class AuditLog(Base):
    """
    Audit Log model - immutable audit trail with hash chaining.
    
    Requirements:
    - Req 13.1: Append-only audit logging
    - Req 13.2: Hash chaining for tamper detection
    - Req 13.3: Comprehensive audit data capture
    - Req 13.4: Audit flag tracking
    
    Immutability enforced by database triggers (see migration).
    """
    __tablename__ = "audit_logs"

    # Primary Key
    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Multi-tenancy
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Timestamp (ISO 8601 format)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Photo Capture Context
    vendor_id = Column(String(6), nullable=False, index=True)
    photo_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    campaign_code = Column(String(50), nullable=False, index=True)
    
    # Audit Data (stored as JSONB for flexibility)
    sensor_data = Column(JSONB, nullable=False)
    signature = Column(JSONB, nullable=False)
    device_info = Column(JSONB, nullable=False)
    
    # Hash Chaining (SHA-256)
    previous_record_hash = Column(String(64), nullable=True)  # NULL for first record
    record_hash = Column(String(64), nullable=False)  # Hash of current record
    
    # Audit Flags
    audit_flags = Column(ARRAY(Text), default=list)
    
    # Creation timestamp (for record keeping)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AuditLog(audit_id={self.audit_id}, vendor_id={self.vendor_id}, timestamp={self.timestamp})>"


# Composite indexes for efficient querying
Index('idx_audit_logs_vendor_timestamp', AuditLog.vendor_id, AuditLog.timestamp.desc())
Index('idx_audit_logs_campaign_timestamp', AuditLog.campaign_code, AuditLog.timestamp.desc())
