"""
Photo model - stores captured photo metadata and verification status.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Float, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class VerificationStatus(str, enum.Enum):
    """Photo verification status enumeration."""
    PENDING = "pending"
    VERIFIED = "verified"
    FLAGGED = "flagged"
    REJECTED = "rejected"


class Photo(Base):
    """
    Photo model - captured photo metadata and verification results.

    Requirements:
    - Req 9.1: Photo upload and storage
    - Req 9.3: S3 storage with thumbnails
    - Req 7.5-7.8: Location profile matching results
    - Req 27.1-27.3: Signature verification status
    """
    __tablename__ = "photos"

    # Primary Key
    photo_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Multi-tenancy
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Associations
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.campaign_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    vendor_id = Column(
        String(6),
        ForeignKey("vendors.vendor_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Timestamps
    capture_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    upload_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)

    # S3 Storage
    s3_key = Column(String(500), nullable=False)
    thumbnail_s3_key = Column(String(500), nullable=True)

    # Verification Results — FIX: values_callable to send lowercase enum values to PostgreSQL
    verification_status = Column(
        SQLEnum(VerificationStatus, name="verificationstatus", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=VerificationStatus.PENDING,
        index=True
    )
    signature_valid = Column(Boolean, nullable=True)
    location_match_score = Column(Float, nullable=True)
    distance_from_expected = Column(Float, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)

    # Relationships
    campaign = relationship("Campaign", back_populates="photos")
    vendor = relationship("Vendor", back_populates="photos")
    sensor_data = relationship(
        "SensorData",
        back_populates="photo",
        uselist=False,
        cascade="all, delete-orphan"
    )
    signature = relationship(
        "PhotoSignature",
        back_populates="photo",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<Photo(photo_id={self.photo_id}, campaign={self.campaign_id}, "
            f"status={self.verification_status})>"
        )
