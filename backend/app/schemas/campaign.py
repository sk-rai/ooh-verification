"""Pydantic schemas for campaign management endpoints."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class LocationProfileCreate(BaseModel):
    """Schema for creating a location profile within a campaign."""
    expected_latitude: Optional[float] = Field(None, ge=-90, le=90, description="Expected GPS latitude. Auto-resolved from address if not provided.")
    expected_longitude: Optional[float] = Field(None, ge=-180, le=180, description="Expected GPS longitude. Auto-resolved from address if not provided.")
    address: Optional[str] = Field(None, max_length=500, description="Street address. Will be geocoded to lat/lng if coordinates not provided.")
    tolerance_meters: float = Field(50.0, gt=0, description="GPS tolerance radius in meters")
    expected_wifi_bssids: Optional[List[str]] = Field(None, description="Expected WiFi BSSIDs (MAC addresses)")
    expected_cell_tower_ids: Optional[List[int]] = Field(None, description="Expected cell tower IDs")
    expected_pressure_min: Optional[float] = Field(None, description="Minimum expected pressure in hPa")
    expected_pressure_max: Optional[float] = Field(None, description="Maximum expected pressure in hPa")
    expected_light_min: Optional[float] = Field(None, description="Minimum expected light in lux")
    expected_light_max: Optional[float] = Field(None, description="Maximum expected light in lux")
    expected_magnetic_min: Optional[float] = Field(None, description="Minimum expected magnetic field in µT")
    expected_magnetic_max: Optional[float] = Field(None, description="Maximum expected magnetic field in µT")
    delivery_window_start: Optional[datetime] = Field(None, description="Delivery window start (ISO 8601). Required for delivery campaigns.")
    delivery_window_end: Optional[datetime] = Field(None, description="Delivery window end (ISO 8601). Required for delivery campaigns.")

    class Config:
        json_schema_extra = {
            "example": {
                "expected_latitude": 40.7128000,
                "expected_longitude": -74.0060000,
                "tolerance_meters": 50.0,
                "expected_wifi_bssids": ["00:11:22:33:44:55", "AA:BB:CC:DD:EE:FF"],
                "expected_cell_tower_ids": [12345, 67890],
                "expected_pressure_min": 1010.0,
                "expected_pressure_max": 1020.0,
                "expected_light_min": 100.0,
                "expected_light_max": 500.0,
                "expected_magnetic_min": 40.0,
                "expected_magnetic_max": 60.0
            }
        }



class LocationProfileResponse(BaseModel):
    """Schema for location profile response."""
    profile_id: UUID
    campaign_id: UUID
    expected_latitude: float
    expected_longitude: float
    tolerance_meters: float
    expected_wifi_bssids: Optional[List[str]]
    expected_cell_tower_ids: Optional[List[int]]
    expected_pressure_min: Optional[float]
    expected_pressure_max: Optional[float]
    expected_light_min: Optional[float]
    expected_light_max: Optional[float]
    expected_magnetic_min: Optional[float]
    expected_magnetic_max: Optional[float]
    delivery_window_start: Optional[datetime]
    delivery_window_end: Optional[datetime]
    resolved_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CampaignCreate(BaseModel):
    """Schema for creating a new campaign."""
    name: str = Field(..., min_length=2, max_length=255, description="Campaign name")
    campaign_type: str = Field(..., description="Campaign type (ooh, construction, insurance, delivery, healthcare, property_management)")
    start_date: datetime = Field(..., description="Campaign start date")
    end_date: datetime = Field(..., description="Campaign end date")
    location_profile: Optional[LocationProfileCreate] = Field(None, description="Single location (backward compat)")
    locations: Optional[list] = Field(None, description="Multiple locations [{expected_latitude, expected_longitude, tolerance_meters, address}]")

    @field_validator('campaign_type')
    @classmethod
    def validate_campaign_type(cls, v):
        valid_types = ['ooh', 'construction', 'insurance', 'delivery', 'healthcare', 'property_management']
        if v not in valid_types:
            raise ValueError(f"Invalid campaign type. Must be one of: {', '.join(valid_types)}")
        return v

    @field_validator('end_date')
    @classmethod
    def validate_dates(cls, v, info):
        if 'start_date' in info.data and v <= info.data['start_date']:
            raise ValueError("end_date must be after start_date")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Times Square Billboard Campaign",
                "campaign_type": "ooh",
                "start_date": "2026-04-01T00:00:00Z",
                "end_date": "2026-04-30T23:59:59Z",
                "location_profile": {
                    "expected_latitude": 40.7580,
                    "expected_longitude": -73.9855,
                    "tolerance_meters": 50.0
                }
            }
        }



class CampaignUpdate(BaseModel):
    """Schema for updating campaign information."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    status: Optional[str] = Field(None, description="Campaign status (active, completed, cancelled)")
    end_date: Optional[datetime] = Field(None, description="Campaign end date")
    locations: Optional[list] = Field(None, description="Replace all locations [{expected_latitude, expected_longitude, tolerance_meters, address}]")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v is not None:
            valid_statuses = ['active', 'completed', 'cancelled']
            if v not in valid_statuses:
                raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Updated Campaign Name",
                "status": "completed"
            }
        }


class CampaignResponse(BaseModel):
    """Schema for campaign response."""
    campaign_id: UUID
    campaign_code: str
    name: str
    campaign_type: str
    client_id: UUID
    start_date: datetime
    end_date: datetime
    status: str
    created_at: datetime
    updated_at: datetime
    location_profile: Optional[List[LocationProfileResponse]] = Field(None, description="Location profiles for this campaign")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
                "campaign_code": "NYC-2026-A3X9",
                "name": "Times Square Billboard Campaign",
                "campaign_type": "ooh",
                "client_id": "660e8400-e29b-41d4-a716-446655440000",
                "start_date": "2026-04-01T00:00:00Z",
                "end_date": "2026-04-30T23:59:59Z",
                "status": "active",
                "created_at": "2026-03-04T12:00:00Z",
                "updated_at": "2026-03-04T12:00:00Z",
                "location_profile": []
            }
        }


class CampaignListResponse(BaseModel):
    """Schema for campaign list response."""
    campaigns: List[CampaignResponse]
    total: int

    class Config:
        json_schema_extra = {
            "example": {
                "campaigns": [],
                "total": 0
            }
        }


class VendorAssignmentCreate(BaseModel):
    """Schema for assigning vendors to a campaign."""
    vendor_ids: List[str] = Field(..., min_length=1, description="List of vendor IDs to assign")

    class Config:
        json_schema_extra = {
            "example": {
                "vendor_ids": ["A3X9K2", "B7Y4M1"]
            }
        }


class VendorAssignmentResponse(BaseModel):
    """Schema for vendor assignment response."""
    assignment_id: UUID
    campaign_id: UUID
    vendor_id: str
    assigned_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
