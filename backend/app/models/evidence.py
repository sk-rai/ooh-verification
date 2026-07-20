"""
Evidence model - unified model for all capture types (photo, video, voice, text).

Replaces/extends the photos table for new captures while maintaining backward compatibility.
"""
from sqlalchemy import Column, String, Float, Integer, BigInteger, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class EvidenceType(str, enum.Enum):
    """Evidence type enumeration."""
    PHOTO = "photo"
    VIDEO = "video"
    VOICE_NOTE = "voice_note"
    TEXT_NOTE = "text_note"


class EvidenceStatus(str, enum.Enum):
    """Verification status for evidence."""
    PENDING = "pending"
    VERIFIED = "verified"
    FLAGGED = "flagged"
    REJECTED = "rejected"


class Evidence(Base):
    """
    Unified evidence model supporting multiple media types.

    Supports: photos, videos, voice notes, and text notes.
    Campaign is optional (allows quick capture / event-driven evidence).
    """
    __tablename__ = "evidence"

    # Primary Key
    evidence_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Multi-tenancy
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Relationships (campaign is OPTIONAL for quick capture)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.campaign_id", ondelete="SET NULL"), nullable=True, index=True)
    vendor_id = Column(String(6), ForeignKey("vendors.vendor_id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.case_id", ondelete="SET NULL"), nullable=True, index=True)

    # Type & Category
    evidence_type = Column(String(20), nullable=False, index=True)  # photo, video, voice_note, text_note
    category = Column(String(50), nullable=True, index=True)  # accident, damage, inspection, delivery_proof, hazard, other

    # File Storage
    file_key = Column(String(500), nullable=True)  # S3/Cloudinary key
    file_url = Column(String(500), nullable=True)
    thumbnail_key = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    mime_type = Column(String(50), nullable=True)
    duration_seconds = Column(Float, nullable=True)  # For video/voice

    # Text Content (for text_note type, or notes attached to any media)
    text_content = Column(Text, nullable=True)

    # Capture Context
    capture_timestamp = Column(DateTime(timezone=True), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)

    # Verification
    verification_status = Column(String(20), nullable=False, default="pending", index=True)
    verification_confidence = Column(Float, nullable=True)
    verification_flags = Column(JSONB, nullable=True, default=list)

    # Security
    device_signature = Column(Text, nullable=True)
    file_hash = Column(String(128), nullable=True)  # SHA-256 of uploaded file

    # Sensor Data (embedded for simplicity — full sensor data in separate table if needed)
    sensor_data = Column(JSONB, nullable=True)  # GPS, WiFi, cell, pressure, magnetic, etc.

    # Metadata
    tags = Column(JSONB, nullable=True, default=list)
    extra_metadata = Column("metadata", JSONB, nullable=True, default=dict)  # Flexible: extra device info, etc.

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), onupdate=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)

    # Relationships
    campaign = relationship("Campaign", backref="evidence_items")
    vendor = relationship("Vendor", backref="evidence_items")
    gps_track = relationship("GpsTrack", back_populates="evidence", uselist=False, cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("ix_evidence_tenant_type", "tenant_id", "evidence_type"),
        Index("ix_evidence_campaign_vendor", "campaign_id", "vendor_id"),
        Index("ix_evidence_created", "created_at"),
    )

    def __repr__(self):
        return f"<Evidence(id={self.evidence_id}, type={self.evidence_type}, status={self.verification_status})>"


class GpsTrack(Base):
    """GPS track recorded during video capture (1-second intervals)."""
    __tablename__ = "gps_tracks"

    track_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_id = Column(UUID(as_uuid=True), ForeignKey("evidence.evidence_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    points = Column(JSONB, nullable=False)  # [{lat, lon, accuracy, timestamp_ms}, ...]
    duration_seconds = Column(Float, nullable=True)
    total_distance_meters = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)

    # Relationship
    evidence = relationship("Evidence", back_populates="gps_track")

    def __repr__(self):
        return f"<GpsTrack(evidence_id={self.evidence_id}, points={len(self.points) if self.points else 0})>"


class Case(Base):
    """Case/incident for grouping related evidence captures."""
    __tablename__ = "cases"

    case_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="open")  # open, closed, archived
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), onupdate=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)

    # Relationships
    evidence_items = relationship("Evidence", backref="case")

    def __repr__(self):
        return f"<Case(id={self.case_id}, title='{self.title}', status={self.status})>"
