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
    ssid: Optional[str] = Field(None, description="Network SSID")
    bssid: str = Field(..., description="MAC address (BSSID)")
    signal_strength: Optional[int] = Field(None, description="Signal strength in dBm")
    signal_dbm: Optional[int] = Field(None, description="Signal strength in dBm (Android format)")
    frequency: Optional[int] = Field(None, description="Frequency in MHz")
    frequency_mhz: Optional[int] = Field(None, description="Frequency in MHz (Android format)")



class CellTower(BaseModel):
    """Cell tower data schema."""
    cell_id: int = Field(..., description="Cell tower ID")
    lac: int = Field(..., description="Location Area Code")
    mcc: int = Field(..., description="Mobile Country Code")
    mnc: int = Field(..., description="Mobile Network Code")
    signal_strength: Optional[int] = Field(None, description="Signal strength in dBm")
    signal_dbm: Optional[int] = Field(None, description="Signal strength in dBm (Android format)")
    network_type: Optional[str] = Field(None, description="Network type (LTE, 5G, etc)")


class EnvironmentalData(BaseModel):
    """Environmental sensor data schema. Accepts both backend and Android field names."""
    # Backend field names
    barometer_pressure: Optional[float] = Field(None, description="Atmospheric pressure in hPa")
    barometer_altitude: Optional[float] = Field(None, description="Derived altitude in meters")
    ambient_light_lux: Optional[float] = Field(None, description="Illuminance in lux")
    magnetic_field_x: Optional[float] = Field(None, description="Magnetic field X in uT")
    magnetic_field_y: Optional[float] = Field(None, description="Magnetic field Y in uT")
    magnetic_field_z: Optional[float] = Field(None, description="Magnetic field Z in uT")
    magnetic_field_magnitude: Optional[float] = Field(None, description="Magnetic field magnitude in uT")
    hand_tremor_frequency: Optional[float] = Field(None, description="Hand tremor frequency in Hz")
    hand_tremor_is_human: Optional[bool] = Field(None, description="Is tremor in human range")
    hand_tremor_confidence: Optional[float] = Field(None, description="Tremor detection confidence (0-1)")
    # Android field names (aliases)
    pressure_hpa: Optional[float] = Field(None, description="Pressure in hPa (Android format)")
    altitude_meters: Optional[float] = Field(None, description="Altitude in meters (Android format)")
    light_lux: Optional[float] = Field(None, description="Light in lux (Android format)")
    magnetic_field: Optional[Dict[str, Any]] = Field(None, description="Magnetic field object (Android format)")
    tremor_detected: Optional[bool] = Field(None, description="Tremor detected flag (Android format)")


    def normalize(self):
        """Normalize Android field names to backend field names."""
        if self.pressure_hpa is not None and self.barometer_pressure is None:
            self.barometer_pressure = self.pressure_hpa
        if self.altitude_meters is not None and self.barometer_altitude is None:
            self.barometer_altitude = self.altitude_meters
        if self.light_lux is not None and self.ambient_light_lux is None:
            self.ambient_light_lux = self.light_lux
        if self.magnetic_field is not None:
            if self.magnetic_field_x is None and 'x' in self.magnetic_field:
                self.magnetic_field_x = self.magnetic_field['x']
            if self.magnetic_field_y is None and 'y' in self.magnetic_field:
                self.magnetic_field_y = self.magnetic_field['y']
            if self.magnetic_field_z is None and 'z' in self.magnetic_field:
                self.magnetic_field_z = self.magnetic_field['z']
            if self.magnetic_field_magnitude is None and 'magnitude' in self.magnetic_field:
                self.magnetic_field_magnitude = self.magnetic_field['magnitude']


class SensorDataSchema(BaseModel):
    """Complete sensor data schema for photo upload. Accepts both backend and Android formats."""
    gps: GPSData = Field(..., description="GPS data")
    # Backend format
    wifi_networks: Optional[List[WiFiNetwork]] = Field(None, description="WiFi networks detected")
    cell_towers: Optional[List[CellTower]] = Field(None, description="Cell towers detected")
    environmental: Optional[EnvironmentalData] = Field(None, description="Environmental sensor data")
    # Android format (nested objects with 'networks'/'towers' lists)
    wifi: Optional[Dict[str, Any]] = Field(None, description="WiFi data (Android format)")
    cell: Optional[Dict[str, Any]] = Field(None, description="Cell data (Android format)")
    # Common fields
    location_hash: Optional[str] = Field(None, description="SHA-256 hash of location data")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="Overall confidence score")
    schema_version: str = Field(default="2.0", description="Schema version")


    def __init__(self, **data):
        """Normalize Android format to backend format on init."""
        # Handle Android wifi format: {"networks": [...], "count": N}
        if 'wifi' in data and data['wifi'] and 'wifi_networks' not in data:
            wifi_data = data['wifi']
            if isinstance(wifi_data, dict) and 'networks' in wifi_data:
                networks = []
                for n in wifi_data['networks']:
                    networks.append(WiFiNetwork(
                        ssid=n.get('ssid'),
                        bssid=n.get('bssid', ''),
                        signal_strength=n.get('signal_strength') or n.get('signal_dbm'),
                        frequency=n.get('frequency') or n.get('frequency_mhz'),
                    ))
                data['wifi_networks'] = networks

        # Handle Android cell format: {"towers": [...], "count": N}
        if 'cell_towers' not in data:
            cell_data = data.get('cell') or data.get('cell_towers_data')
            if isinstance(cell_data, dict) and 'towers' in cell_data:
                towers = []
                for t in cell_data['towers']:
                    towers.append(CellTower(
                        cell_id=t.get('cell_id', 0),
                        lac=t.get('lac', 0),
                        mcc=t.get('mcc', 0),
                        mnc=t.get('mnc', 0),
                        signal_strength=t.get('signal_strength') or t.get('signal_dbm'),
                        network_type=t.get('network_type'),
                    ))
                data['cell_towers'] = towers

        super().__init__(**data)

        # Normalize environmental data
        if self.environmental:
            self.environmental.normalize()



class PhotoSignatureSchema(BaseModel):
    """Photo signature schema for upload."""
    signature: str = Field(..., description="Base64 encoded signature")
    algorithm: str = Field(..., description="Signature algorithm")
    timestamp: datetime = Field(..., description="Signature generation timestamp")
    location_hash: str = Field(..., description="SHA-256 hash of location data")
    device_id: str = Field(..., description="Device identifier")

    @field_validator('algorithm')
    @classmethod
    def validate_algorithm(cls, v):
        valid_algorithms = ['RSA-2048', 'ECDSA-P256', 'ECDSA-SHA256']
        if v not in valid_algorithms:
            raise ValueError(f"Invalid algorithm. Must be one of: {', '.join(valid_algorithms)}")
        return v


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
