"""
Vendor-Client Association model — many-to-many relationship.

A vendor (freelancer) can work for multiple clients (companies).
Same phone number = same vendor across companies.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class AssociationStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class VendorClientAssociation(Base):
    """
    Links vendors to clients (companies).

    A vendor can be associated with multiple clients.
    A client can have multiple vendors.
    """
    __tablename__ = "vendor_client_associations"

    __table_args__ = (
        UniqueConstraint('vendor_id', 'client_id', name='uq_vendor_client'),
    )

    association_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    vendor_id = Column(
        String(6),
        ForeignKey("vendors.vendor_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.client_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    status = Column(
        SQLEnum(AssociationStatus, name="associationstatus", native_enum=True,
                values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AssociationStatus.ACTIVE,
        server_default="active"
    )

    enrolled_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    vendor = relationship("Vendor", back_populates="client_associations")
    client = relationship("Client", back_populates="vendor_associations")

    def __repr__(self):
        return f"<VendorClientAssociation(vendor={self.vendor_id}, client={self.client_id}, status={self.status})>"
