"""
Campaign Location model - represents physical locations for campaigns.
"""
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class CampaignLocation(Base):
    """
    Campaign Location model - defines physical locations where photos should be captured.
    
    Features:
    - Multiple locations per campaign
    - Geocoded addresses with lat/lng coordinates
    - Verification radius for location matching
    - Address components for detailed location info
    """
    __tablename__ = "campaign_locations"

    # Primary Key
    location_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Multi-tenancy
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Campaign Reference
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.campaign_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Location Name/Description
    name = Column(String(255), nullable=False)  # e.g., "Billboard Site A", "Construction Site North"
    description = Column(Text, nullable=True)
    
    # Address Information
    address = Column(String(500), nullable=False)  # Full formatted address
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    
    # Geocoded Coordinates
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    
    # Verification Settings
    verification_radius_meters = Column(
        Integer,
        nullable=False,
        default=100,  # Default 100 meters radius
        comment="Acceptable distance from location for photo verification"
    )
    
    # Geocoding Metadata
    geocoding_accuracy = Column(String(50), nullable=True)  # e.g., "ROOFTOP", "APPROXIMATE"
    place_id = Column(String(255), nullable=True)  # Google Place ID or similar
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="locations")

    def __repr__(self):
        return f"<CampaignLocation(location_id={self.location_id}, name={self.name}, lat={self.latitude}, lng={self.longitude})>"
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "location_id": str(self.location_id),
            "campaign_id": str(self.campaign_id),
            "name": self.name,
            "description": self.description,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "postal_code": self.postal_code,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "verification_radius_meters": self.verification_radius_meters,
            "geocoding_accuracy": self.geocoding_accuracy,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
