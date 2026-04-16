"""
Sensor Data model - stores multi-sensor verification data.
"""
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class SensorData(Base):
    """
    Sensor Data model - comprehensive sensor readings for photo verification.
    
    Requirements:
    - Req 3.1-3.7: GPS data with 7 decimal precision
    - Req 4.1-4.8: WiFi network fingerprinting
    - Req 5.1-5.7: Cell tower identification
    - Req 6.1-6.6: Multi-sensor triangulation
    - Req 30.1-30.6: GPS accuracy validation
    - Property 2: Round-trip sensor data serialization
    - Property 11: Sensor data completeness
    """
    __tablename__ = "sensor_data"

    # Primary Key
    sensor_data_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Photo Association
    photo_id = Column(
        UUID(as_uuid=True),
        ForeignKey("photos.photo_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One sensor data per photo
        index=True
    )
    
    # GPS Data (7 decimal precision = ~1.1cm accuracy)
    gps_latitude = Column(Float(precision=10), nullable=True)
    gps_longitude = Column(Float(precision=10), nullable=True)
    gps_altitude = Column(Float, nullable=True)  # Meters
    gps_accuracy = Column(Float, nullable=True)  # Horizontal accuracy in meters
    gps_provider = Column(String(20), nullable=True)  # 'GPS', 'NETWORK', 'FUSED'
    gps_satellite_count = Column(Integer, nullable=True)
    
    # WiFi Networks (JSONB array)
    # Format: [{"ssid": "Network1", "bssid": "00:11:22:33:44:55", "signal_strength": -45, "frequency": 2437}]
    wifi_networks = Column(JSONB, nullable=True)
    
    # Cell Towers (JSONB array)
    # Format: [{"cell_id": 12345, "lac": 100, "mcc": 404, "mnc": 45, "signal_strength": -75, "network_type": "LTE"}]
    cell_towers = Column(JSONB, nullable=True)
    
    # Barometer (Atmospheric Pressure)
    barometer_pressure = Column(Float, nullable=True)  # hPa (hectopascals)
    barometer_altitude = Column(Float, nullable=True)  # Derived altitude in meters
    
    # Ambient Light Sensor
    ambient_light_lux = Column(Float, nullable=True)  # Illuminance in lux
    
    # Magnetometer (Magnetic Field)
    magnetic_field_x = Column(Float, nullable=True)  # μT (microtesla)
    magnetic_field_y = Column(Float, nullable=True)
    magnetic_field_z = Column(Float, nullable=True)
    magnetic_field_magnitude = Column(Float, nullable=True)
    
    # Hand Tremor Detection (Accelerometer/Gyroscope)
    hand_tremor_frequency = Column(Float, nullable=True)  # Hz
    hand_tremor_is_human = Column(Boolean, nullable=True)  # 8-12Hz range check
    hand_tremor_confidence = Column(Float, nullable=True)  # 0-1 confidence score
    
    # Motion Sensors (schema v2.1) — stored as JSONB {x, y, z}
    accelerometer_data = Column(JSONB, nullable=True)  # {x, y, z} in m/s²
    gyroscope_data = Column(JSONB, nullable=True)  # {x, y, z} in rad/s
    orientation_data = Column(JSONB, nullable=True)  # {x, y, z} in degrees

    # Location Hash and Confidence
    location_hash = Column(String(64), nullable=True)  # SHA-256 hash of combined sensor data
    confidence_score = Column(Float, nullable=True)  # 0-1 overall confidence
    
    # Schema Version (for backward compatibility)
    schema_version = Column(String(10), nullable=False, default="2.0")
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)
    
    # Relationships
    photo = relationship("Photo", back_populates="sensor_data")

    def __repr__(self):
        return (
            f"<SensorData(sensor_data_id={self.sensor_data_id}, "
            f"gps=({self.gps_latitude:.7f if self.gps_latitude else None}, "
            f"{self.gps_longitude:.7f if self.gps_longitude else None}), "
            f"confidence={self.confidence_score})>"
        )
