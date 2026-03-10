"""
Pydantic schemas for campaign locations.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class CampaignLocationBase(BaseModel):
    """Base schema for campaign location."""
    name: str = Field(..., min_length=1, max_length=255, description="Location name or identifier")
    description: Optional[str] = Field(None, description="Optional location description")
    address: str = Field(..., min_length=1, max_length=500, description="Full address")
    verification_radius_meters: int = Field(
        default=100,
        ge=10,
        le=10000,
        description="Acceptable distance from location for verification (10m - 10km)"
    )


class CampaignLocationCreate(CampaignLocationBase):
    """Schema for creating a campaign location with address (will be geocoded)."""
    # Address will be geocoded to get lat/lng
    pass


class CampaignLocationCreateWithCoords(CampaignLocationBase):
    """Schema for creating a campaign location with explicit coordinates."""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    geocoding_accuracy: Optional[str] = Field(None, max_length=50)
    place_id: Optional[str] = Field(None, max_length=255)


class CampaignLocationUpdate(BaseModel):
    """Schema for updating a campaign location."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    address: Optional[str] = Field(None, min_length=1, max_length=500)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    verification_radius_meters: Optional[int] = Field(None, ge=10, le=10000)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)


class CampaignLocationResponse(BaseModel):
    """Schema for campaign location response."""
    location_id: str
    campaign_id: str
    name: str
    description: Optional[str]
    address: str
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    postal_code: Optional[str]
    latitude: float
    longitude: float
    verification_radius_meters: int
    geocoding_accuracy: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class GeocodeRequest(BaseModel):
    """Schema for geocoding request."""
    address: str = Field(..., min_length=1, max_length=500, description="Address to geocode")


class ReverseGeocodeRequest(BaseModel):
    """Schema for reverse geocoding request."""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")


class GeocodeResponse(BaseModel):
    """Schema for geocoding response."""
    latitude: float
    longitude: float
    formatted_address: str
    accuracy: str
    place_id: Optional[str]
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    postal_code: Optional[str]


class LocationVerificationResponse(BaseModel):
    """Schema for location verification response."""
    is_valid: bool
    distance_meters: float
    nearest_location_id: Optional[str]
    nearest_location_name: Optional[str]
    message: str
