"""
Campaign Vendor Assignment model - many-to-many relationship.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class CampaignVendorAssignment(Base):
    """
    Campaign Vendor Assignment - links vendors to campaigns.
    
    Requirements:
    - Req 1.3: Vendor assignment to campaigns
    """
    __tablename__ = "campaign_vendor_assignments"
    
    # Composite unique constraint to prevent duplicate assignments
    __table_args__ = (
        UniqueConstraint('campaign_id', 'vendor_id', name='uq_campaign_vendor'),
    )

    # Primary Key
    assignment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Foreign Keys
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
    
    # Timestamp
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="vendor_assignments")
    vendor = relationship("Vendor", back_populates="campaign_assignments")

    def __repr__(self):
        return f"<CampaignVendorAssignment(campaign_id={self.campaign_id}, vendor_id={self.vendor_id})>"
