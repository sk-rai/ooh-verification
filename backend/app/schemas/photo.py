"""
Pydantic schemas for photo upload and management endpoints.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class GPSData(BaseModel):
    """GPS sensor data schema."""
    latitude: float = Field(..., ge=-90, le=90, description="GPS latitude")
    longitude: float = Field(..., ge=-180, le=180, description="GPS longitude")
    altitude: Optional[float] = Field(None, description="Altitude in meters")
    accuracy: Optional[float] = Field(None, description="Horizontal accuracy in meters")
    provider: Optional[str] = Field(None, description="GPS provider (GPS, NETWORK, FUSED)")
    satellite_count: Optional[int] = Field(None, description="Number of satellites")


class WiFiNetwork(BaseModel):
    """WiFi network data schema."""
    ssid: str = Field(..., description="Network SSID")
    bssid: str = Field(..., description="MAC address (BSSID)")
    signal_strength: int = Field(..., description="Signal strength in dBm")
    frequency: Optional[int] = Field(None, description="Frequency in MHz")


class CellTower(BaseModel):
    """Cell tower data schema."""
    cell_id: int = Field(..., description="Cell tower ID")
    lac: int = Field(..., description="Location Area Code")
    mcc: int = Field(..., description="Mobile Country Code")
    mnc: int = Field(..., description="Mobile Network Code")
    signal_strength: int = Field(..., description="Signal strength in dBm")
    network_type: Optional[str] = Field(None, description="Network type (LTE, 5G, etc)")


class EnvironmentalData(BaseModel):
    """Environmental sensor data schema."""
    barometer_pressure: Optional[float] = Field(None, description="Atmospheric pressure in hPa")
    barometer_altitude: Optional[float] = Field(None, description="Derived altitude in meters")
    ambient_light_lux: Optional[float] = Field(None, description="Illuminance in lux")
    magnetic_field_x: Optional[float] = Field(None, description="Magnetic field X in μT")
    magnetic_field_y: Optional[float] = Field(None, description="Magnetic field Y in μT")
    magnetic_field_z: Optional[float] = Field(None, description="Magnetic field Z in μT")
    magnetic_field_magnitude: Optional[float] = Field(None, description="Magnetic field magnitude in μT")
    hand_tremor_frequency: Optional[float] = Field(None, description="Hand tremor frequency in Hz")
    hand_tremor_is_human: Optional[bool] = Field(None, description="Is tremor in human range (8-12Hz)")
    hand_tremor_confidence: Optional[float] = Field(None, description="Tremor detection confidence (0-1)")


class SensorDataSchema(BaseModel):
    """Complete sensor data schema for photo upload."""
    gps: GPSData = Field(..., description="GPS data")
    wifi_networks: Optional[List[WiFiNetwork]] = Field(None, description="WiFi networks detected")
    cell_towers: Optional[List[CellTower]] = Field(None, description="Cell towers detected")
    environmental: Optional[EnvironmentalData] = Field(None, description="Environmental sensor data")
    location_hash: Optional[str] = Field(None, description="SHA-256 hash of location data")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="Overall confidence score")
    schema_version: str = Field(default="2.0", description="Schema version")

    class Config:
        json_schema_extra = {
            "example": {
                "gps": {
                    "latitude": 40.7580,
                    "longitude": -73.9855,
                    "altitude": 10.5,
                    "accuracy": 5.0,
                    "provider": "GPS",
                    "satellite_count": 12
                },
                "wifi_networks": [
                    {
                        "ssid": "CoffeeShop-WiFi",
                        "bssid": "00:11:22:33:44:55",
                        "signal_strength": -45,
                        "frequency": 2437
                    }
                ],
                "cell_towers": [
                    {
                        "cell_id": 12345,
                        "lac": 100,
                        "mcc": 310,
                        "mnc": 260,
                        "signal_strength": -75,
                        "network_type": "LTE"
                    }
                ],
                "environmental": {
                    "barometer_pressure": 1013.25,
                    "ambient_light_lux": 250.0
                },
                "location_hash": "abc123...",
                "confidence_score": 0.95,
                "schema_version": "2.0"
            }
        }


class PhotoSignatureSchema(BaseModel):
    """Photo signature schema for upload."""
    signature: str = Field(..., description="Base64 encoded signature")
    algorithm: str = Field(..., description="Signature algorithm (RSA-2048 or ECDSA-P256)")
    timestamp: datetime = Field(..., description="Signature generation timestamp")
    location_hash: str = Field(..., description="SHA-256 hash of location data")
    device_id: str = Field(..., description="Device identifier")

    @field_validator('algorithm')
    @classmethod
    def validate_algorithm(cls, v):
        valid_algorithms = ['RSA-2048', 'ECDSA-P256']
        if v not in valid_algorithms:
            raise ValueError(f"Invalid algorithm. Must be one of: {', '.join(valid_algorithms)}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "signature": "base64encodedstring...",
                "algorithm": "RSA-2048",
                "timestamp": "2026-04-15T14:30:00Z",
                "location_hash": "abc123...",
                "device_id": "device-12345"
            }
        }


class PhotoUploadResponse(BaseModel):
    """Response schema for photo upload."""
    photo_id: UUID
    verification_status: str
    signature_valid: bool
    location_match_score: Optional[float] = Field(None, description="Location match score (0-100)")
    distance_from_expected: Optional[float] = Field(None, description="Distance from expected location in meters")
    s3_url: str
    thumbnail_url: Optional[str] = None
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "photo_id": "550e8400-e29b-41d4-a716-446655440000",
                "verification_status": "verified",
                "signature_valid": True,
                "location_match_score": 95.5,
                "distance_from_expected": 12.3,
                "s3_url": "https://s3.amazonaws.com/bucket/photos/...",
                "thumbnail_url": "https://s3.amazonaws.com/bucket/thumbnails/...",
                "message": "Photo uploaded and verified successfully"
            }
        }


class PhotoResponse(BaseModel):
    """Schema for photo details response."""
    photo_id: UUID
    campaign_id: UUID
    vendor_id: str
    capture_timestamp: datetime
    upload_timestamp: datetime
    s3_key: str
    thumbnail_s3_key: Optional[str]
    verification_status: str
    signature_valid: Optional[bool]
    location_match_score: Optional[float]
    distance_from_expected: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
