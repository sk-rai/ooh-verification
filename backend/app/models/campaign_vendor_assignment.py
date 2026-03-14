"""Campaign Vendor Assignment model - many-to-many relationship."""

from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Float, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class CampaignVendorAssignment(Base):
    """
    Campaign Vendor Assignment - links vendors to campaigns with optional location data.
    
    Requirements:
    - Req 1.3: Vendor assignment to campaigns
    - Req 1.4: Location specification per assignment (address or coordinates)
    """
    __tablename__ = "campaign_vendor_assignments"
    
    # Composite unique constraint to prevent duplicate assignments
    # Check constraint to ensure location data is valid
    __table_args__ = (
        UniqueConstraint('campaign_id', 'vendor_id', name='uq_campaign_vendor'),
        CheckConstraint(
            '(assignment_address IS NULL AND assignment_latitude IS NULL AND assignment_longitude IS NULL) OR '
            '(assignment_address IS NOT NULL) OR '
            '(assignment_latitude IS NOT NULL AND assignment_longitude IS NOT NULL)',
            name='check_location_data'
        ),
    )
    
    # Primary Key
    assignment_id = Column(UUID(as_uuid=True), 
                          primary_key=True, 
                          default=uuid.uuid4, 
                          index=True)
    
    # Foreign Keys
    campaign_id = Column(UUID(as_uuid=True), 
                        ForeignKey("campaigns.campaign_id", ondelete="CASCADE"),
                        nullable=False,
                        index=True)
    
    vendor_id = Column(String(6), 
                      ForeignKey("vendors.vendor_id", ondelete="CASCADE"),
                      nullable=False,
                      index=True)
    
    # Location fields (optional - for specifying where vendor should capture photos)
    assignment_address = Column(String(500), nullable=True)
    assignment_latitude = Column(Float, nullable=True)
    assignment_longitude = Column(Float, nullable=True)
    assignment_location_name = Column(String(255), nullable=True)
    
    # Timestamps
    assigned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)  # Kept for backward compatibility
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), onupdate=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="vendor_assignments")
    vendor = relationship("Vendor", back_populates="campaign_assignments")
    
    def __repr__(self):
        return f"<CampaignVendorAssignment(campaign_id={self.campaign_id}, vendor_id={self.vendor_id})>"
