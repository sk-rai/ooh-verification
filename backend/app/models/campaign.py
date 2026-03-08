"""
Campaign model - represents verification campaigns.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class CampaignType(str, enum.Enum):
    """Campaign type enumeration for different industries."""
    OOH_ADVERTISING = "ooh"
    CONSTRUCTION = "construction"
    INSURANCE = "insurance"
    DELIVERY = "delivery"
    HEALTHCARE = "healthcare"
    PROPERTY_MANAGEMENT = "property_management"


class CampaignStatus(str, enum.Enum):
    """Campaign status enumeration."""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Campaign(Base):
    """
    Campaign model - defines what photos to capture and where.
    
    Requirements:
    - Req 1.1: Campaign creation
    - Req 1.2: Campaign code validation
    - Req 1.4: Campaign expiration dates
    - Req 18.1-18.5: Multi-domain campaign types
    - Property 12: Campaign code format invariant
    """
    __tablename__ = "campaigns"

    # Primary Key
    campaign_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Campaign Identification
    campaign_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    
    # Campaign Type
    campaign_type = Column(
        SQLEnum(CampaignType),
        nullable=False,
        index=True
    )
    
    # Ownership
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.client_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Campaign Duration
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False, index=True)
    
    # Status
    status = Column(
        SQLEnum(CampaignStatus),
        nullable=False,
        default=CampaignStatus.ACTIVE,
        index=True
    )
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    client = relationship("Client", back_populates="campaigns")
    location_profile = relationship(
        "LocationProfile",
        back_populates="campaign",
        uselist=False,
        cascade="all, delete-orphan"
    )
    photos = relationship("Photo", back_populates="campaign", cascade="all, delete-orphan")
    vendor_assignments = relationship(
        "CampaignVendorAssignment",
        back_populates="campaign",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Campaign(campaign_id={self.campaign_id}, code={self.campaign_code}, type={self.campaign_type})>"
