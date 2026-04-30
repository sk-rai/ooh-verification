"""Location Profile model - defines expected sensor patterns for verification."""
from sqlalchemy import Column, Float, ForeignKey, DateTime, ARRAY, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class LocationProfile(Base):
    """Location Profile model - expected sensor data for location verification.

    Requirements:
    - Req 3.1: GPS coordinates with 7 decimal precision
    - Req 7.1-7.4: Location profile matching (GPS, WiFi, cell towers)
    - Req 7.2: GPS tolerance radius
    - Req 7.3: Expected WiFi networks
    - Req 7.4: Expected cell towers
    - Property 7: GPS coordinate precision preservation
    - Task A1: Expected pressure range (auto-populated from elevation)
    - Task A2: Expected magnetic field range (auto-populated from NOAA WMM)
    """
    __tablename__ = "location_profiles"

    # Primary Key
    profile_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )

    # Campaign Association
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.campaign_id", ondelete="CASCADE"),
        nullable=False,
        index=True  # Multiple profiles per campaign (multi-location)
    )

    # GPS Expected Location (7 decimal precision = ~1.1cm accuracy)
    expected_latitude = Column(Float(precision=10), nullable=False)
    expected_longitude = Column(Float(precision=10), nullable=False)
    tolerance_meters = Column(Float, nullable=False, default=50.0)


    # WiFi Expected Networks (array of BSSIDs - MAC addresses)
    expected_wifi_bssids = Column(ARRAY(String), nullable=True)

    # Cell Tower Expected IDs
    expected_cell_tower_ids = Column(ARRAY(Integer), nullable=True)

    # Environmental Sensor Ranges
    expected_pressure_min = Column(Float, nullable=True)  # hPa (hectopascals)
    expected_pressure_max = Column(Float, nullable=True)
    expected_light_min = Column(Float, nullable=True)     # lux
    expected_light_max = Column(Float, nullable=True)

    # Magnetic Field Range (Task A2)
    expected_magnetic_min = Column(Float, nullable=True)  # µT (microtesla)
    expected_magnetic_max = Column(Float, nullable=True)

    # Delivery Verification: Time Window
    delivery_window_start = Column(DateTime(timezone=True), nullable=True)
    delivery_window_end = Column(DateTime(timezone=True), nullable=True)

    # Resolved address (from geocoding)
    resolved_address = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=__import__("datetime").timezone.utc),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=__import__("datetime").timezone.utc),
        onupdate=lambda: datetime.now(tz=__import__("datetime").timezone.utc),
        nullable=False
    )

    # Relationships
    campaign = relationship("Campaign", back_populates="location_profile")

    def __repr__(self):
        return (
            f"<LocationProfile(profile_id={self.profile_id}, "
            f"lat={self.expected_latitude:.7f}, lon={self.expected_longitude:.7f}, "
            f"tolerance={self.tolerance_meters}m)>"
        )
