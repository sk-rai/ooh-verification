"""
Vendor model - represents field workers who capture photos.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base


class VendorStatus(enum.Enum):
    """Vendor status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class Vendor(Base):
    """
    Vendor model - field workers created by clients.

    Requirements:
    - Req 1.1: Vendor creation by clients
    - Req 1.2: Vendor ID generation (6-char alphanumeric)
    - Req 1.3: SMS delivery with vendor ID
    - Req 12.6: Public key storage for signature verification
    """
    __tablename__ = "vendors"

    # Primary Key - 6-character alphanumeric ID (e.g., "A3X9K2")
    vendor_id = Column(String(6), primary_key=True, index=True)

    # Multi-tenancy
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Vendor Information
    name = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=False, index=True)
    email = Column(String(255), nullable=True)

    # Status
    status = Column(
        SQLEnum(VendorStatus, name="vendorstatus", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=VendorStatus.ACTIVE,
        server_default="active",
        index=True
    )

    # Ownership
    created_by_client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.client_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Device Registration (set after first Android app login)
    device_id = Column(String(255), nullable=True, unique=True)
    public_key = Column(String, nullable=True)  # RSA/ECDSA public key from Android Keystore

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    client = relationship("Client", back_populates="vendors")
    photos = relationship("Photo", back_populates="vendor", cascade="all, delete-orphan")
    campaign_assignments = relationship(
        "CampaignVendorAssignment",
        back_populates="vendor",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Vendor(vendor_id={self.vendor_id}, name={self.name}, status={self.status})>"
