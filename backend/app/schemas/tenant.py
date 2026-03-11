"""
Tenant configuration schemas for API requests/responses.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import re


class TenantBase(BaseModel):
    """Base tenant configuration schema."""
    tenant_name: str = Field(..., min_length=1, max_length=255, description="Tenant display name")
    subdomain: Optional[str] = Field(None, min_length=1, max_length=100, description="Subdomain (e.g., 'client1' for client1.trustcapture.com)")
    custom_domain: Optional[str] = Field(None, min_length=1, max_length=255, description="Custom domain (e.g., 'client.com')")
    logo_url: Optional[str] = Field(None, max_length=500, description="URL to tenant logo")
    primary_color: Optional[str] = Field(None, min_length=7, max_length=7, description="Primary brand color (hex format: #RRGGBB)")
    secondary_color: Optional[str] = Field(None, min_length=7, max_length=7, description="Secondary brand color (hex format: #RRGGBB)")
    email_from_name: Optional[str] = Field(None, max_length=255, description="Email sender name")
    email_from_address: Optional[str] = Field(None, max_length=255, description="Email sender address")
    email_templates: Optional[Dict[str, Any]] = Field(None, description="Custom email templates (JSONB)")
    
    @validator('subdomain')
    def validate_subdomain(cls, v):
        """Validate subdomain format (alphanumeric and hyphens only)."""
        if v is not None:
            if not re.match(r'^[a-z0-9-]+$', v):
                raise ValueError('Subdomain must contain only lowercase letters, numbers, and hyphens')
            if v.startswith('-') or v.endswith('-'):
                raise ValueError('Subdomain cannot start or end with a hyphen')
        return v
    
    @validator('primary_color', 'secondary_color')
    def validate_color(cls, v):
        """Validate hex color format."""
        if v is not None:
            if not re.match(r'^#[0-9A-Fa-f]{6}$', v):
                raise ValueError('Color must be in hex format: #RRGGBB')
        return v
    
    @validator('email_from_address')
    def validate_email(cls, v):
        """Validate email format."""
        if v is not None:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v):
                raise ValueError('Invalid email address format')
        return v


class TenantCreate(TenantBase):
    """Schema for creating a new tenant."""
    subdomain: str = Field(..., min_length=1, max_length=100, description="Subdomain (required for creation)")


class TenantUpdate(BaseModel):
    """Schema for updating tenant configuration."""
    tenant_name: Optional[str] = Field(None, min_length=1, max_length=255)
    subdomain: Optional[str] = Field(None, min_length=1, max_length=100)
    custom_domain: Optional[str] = Field(None, min_length=1, max_length=255)
    logo_url: Optional[str] = Field(None, max_length=500)
    primary_color: Optional[str] = Field(None, min_length=7, max_length=7)
    secondary_color: Optional[str] = Field(None, min_length=7, max_length=7)
    email_from_name: Optional[str] = Field(None, max_length=255)
    email_from_address: Optional[str] = Field(None, max_length=255)
    email_templates: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    
    @validator('subdomain')
    def validate_subdomain(cls, v):
        if v is not None:
            if not re.match(r'^[a-z0-9-]+$', v):
                raise ValueError('Subdomain must contain only lowercase letters, numbers, and hyphens')
        return v
    
    @validator('primary_color', 'secondary_color')
    def validate_color(cls, v):
        if v is not None:
            if not re.match(r'^#[0-9A-Fa-f]{6}$', v):
                raise ValueError('Color must be in hex format: #RRGGBB')
        return v


class TenantResponse(TenantBase):
    """Schema for tenant response."""
    tenant_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TenantListResponse(BaseModel):
    """Schema for tenant list response."""
    tenants: list[TenantResponse]
    total: int


class BrandingResponse(BaseModel):
    """Schema for public branding endpoint (no authentication required)."""
    tenant_name: str
    logo_url: Optional[str]
    primary_color: Optional[str]
    secondary_color: Optional[str]
    
    class Config:
        from_attributes = True
