"""
Pydantic schemas for client management endpoints.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID


class ClientProfileUpdate(BaseModel):
    """Schema for updating client profile."""
    company_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone_number: Optional[str] = Field(None, pattern=r'^\+?[1-9]\d{1,14}$')

    class Config:
        schema_extra = {
            "example": {
                "company_name": "Updated Company Name",
                "phone_number": "+1234567890"
            }
        }


class ClientResponse(BaseModel):
    """Schema for client information response."""
    client_id: str
    email: str
    company_name: str
    phone_number: str
    subscription_tier: str
    subscription_status: str
    created_at: datetime
    updated_at: datetime

    @field_validator('client_id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "client_id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "client@example.com",
                "company_name": "Acme Corporation",
                "phone_number": "+1234567890",
                "subscription_tier": "pro",
                "subscription_status": "active",
                "created_at": "2026-03-04T12:00:00Z",
                "updated_at": "2026-03-04T12:00:00Z"
            }
        }


class SubscriptionResponse(BaseModel):
    """Schema for subscription information response."""
    subscription_id: str
    client_id: str
    tier: str
    status: str
    photos_quota: int
    photos_used: int
    current_period_start: datetime
    current_period_end: datetime
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator('subscription_id', 'client_id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "subscription_id": "550e8400-e29b-41d4-a716-446655440001",
                "client_id": "550e8400-e29b-41d4-a716-446655440000",
                "tier": "pro",
                "status": "active",
                "photos_quota": -1,
                "photos_used": 150,
                "current_period_start": "2026-03-01T00:00:00Z",
                "current_period_end": "2026-04-01T00:00:00Z",
                "stripe_subscription_id": "sub_1234567890",
                "stripe_customer_id": "cus_1234567890",
                "created_at": "2026-03-01T00:00:00Z",
                "updated_at": "2026-03-04T12:00:00Z"
            }
        }
