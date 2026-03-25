"""
Pydantic schemas for vendor management endpoints.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class VendorCreate(BaseModel):
    """Schema for creating a new vendor."""
    name: str = Field(..., min_length=2, max_length=255, description="Vendor name")
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$', description="Phone number in E.164 format")
    email: Optional[str] = Field(None, max_length=255, description="Optional email address")
    city: Optional[str] = Field(None, max_length=100, description="City where vendor operates")
    state: Optional[str] = Field(None, max_length=100, description="State/Province")
    country: Optional[str] = Field(None, max_length=100, description="Country")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "phone_number": "+1234567890",
                "email": "john@example.com"
            }
        }


class VendorUpdate(BaseModel):
    """Schema for updating vendor information."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone_number: Optional[str] = Field(None, pattern=r'^\+?[1-9]\d{1,14}$')
    email: Optional[str] = Field(None, max_length=255)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Smith",
                "phone_number": "+1234567890",
                "email": "john.smith@example.com"
            }
        }


class VendorResponse(BaseModel):
    """Schema for vendor information response."""
    vendor_id: str
    name: str
    phone_number: str
    email: Optional[str]
    status: str
    created_by_client_id: str
    device_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]

    @field_validator('created_by_client_id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        from uuid import UUID
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "vendor_id": "A3X9K2",
                "name": "John Doe",
                "phone_number": "+1234567890",
                "email": "john@example.com",
                "status": "active",
                "created_by_client_id": "550e8400-e29b-41d4-a716-446655440000",
                "device_id": None,
                "created_at": "2026-03-04T12:00:00Z",
                "updated_at": "2026-03-04T12:00:00Z",
                "last_login_at": None
            }
        }


class VendorListResponse(BaseModel):
    """Schema for vendor list response."""
    vendors: list[VendorResponse]
    total: int

    class Config:
        json_schema_extra = {
            "example": {
                "vendors": [
                    {
                        "vendor_id": "A3X9K2",
                        "name": "John Doe",
                        "phone_number": "+1234567890",
                        "email": "john@example.com",
                        "status": "active",
                        "created_by_client_id": "550e8400-e29b-41d4-a716-446655440000",
                        "device_id": None,
                        "created_at": "2026-03-04T12:00:00Z",
                        "updated_at": "2026-03-04T12:00:00Z",
                        "last_login_at": None
                    }
                ],
                "total": 1
            }
        }
