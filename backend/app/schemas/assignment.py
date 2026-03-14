"""
Pydantic schemas for campaign-vendor assignments and bulk operations.

Requirements:
- Req 1.1: Single assignment creation
- Req 1.4: Location specification per assignment
- Req 2.1-2.6: Bulk campaign operations
- Req 3.1-3.10: Bulk vendor operations
- Req 4.1-4.11: Bulk assignment operations
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID
from datetime import datetime


# ============================================================================
# Location Schemas
# ============================================================================

class LocationAssignment(BaseModel):
    """
    Location information for vendor assignment.
    
    Requirements:
    - Req 1.4: Location specification (address or coordinates)
    - Property 39: Location data validation
    """
    address: Optional[str] = Field(None, max_length=500, description="Street address")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Longitude coordinate")
    name: Optional[str] = Field(None, max_length=255, description="Location name/label")
    
    @model_validator(mode='after')
    def validate_location(self):
        """
        Validate that either address or coordinates are provided.
        If coordinates, both latitude and longitude must be present.
        """
        has_address = self.address is not None
        has_coords = self.latitude is not None and self.longitude is not None
        
        # At least one must be provided
        if not has_address and not has_coords:
            raise ValueError("Must provide either address or latitude/longitude")
        
        # If one coordinate provided, both must be provided
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Both latitude and longitude must be provided together")
        
        return self


# ============================================================================
# Single Assignment Schemas
# ============================================================================

class VendorAssignmentCreate(BaseModel):
    """
    Schema for assigning vendors to a campaign.
    
    Requirements:
    - Req 1.1: Create campaign-vendor assignments
    - Req 1.4: Optional location per assignment
    """
    vendor_ids: List[str] = Field(..., min_length=1, description="List of vendor IDs to assign")
    location: Optional[LocationAssignment] = Field(None, description="Optional location for this assignment")
    
    @field_validator('vendor_ids')
    @classmethod
    def validate_vendor_ids(cls, v):
        """Validate vendor ID format (6 alphanumeric characters)."""
        for vendor_id in v:
            if len(vendor_id) != 6 or not vendor_id.isalnum():
                raise ValueError(f"Invalid vendor ID format: {vendor_id}. Must be 6 alphanumeric characters.")
        return v


class VendorAssignmentResponse(BaseModel):
    """Response for a single assignment."""
    assignment_id: UUID
    campaign_id: UUID
    vendor_id: str
    assigned_at: datetime
    location: Optional[LocationAssignment] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class VendorAssignmentBatchResponse(BaseModel):
    """Response for batch assignment operation."""
    assignments: List[VendorAssignmentResponse]
    errors: List[str] = Field(default_factory=list)


# ============================================================================
# Bulk Operation Schemas
# ============================================================================

class BulkOperationRow(BaseModel):
    """
    Result for a single row in bulk operation.
    
    Requirements:
    - Req 2.6, 3.10, 4.7: Operation report structure
    """
    row: int = Field(..., description="Row number in CSV (1-indexed)")
    status: Literal["success", "error"] = Field(..., description="Operation status")
    data: Optional[Dict[str, Any]] = Field(None, description="Created entity data (on success)")
    error: Optional[str] = Field(None, description="Error message (on failure)")


class BulkOperationResponse(BaseModel):
    """
    Response for bulk operations.
    
    Requirements:
    - Req 2.5, 3.7, 4.6: Partial success handling
    - Req 2.6, 3.10, 4.7: Operation report correctness
    - Property 11: Operation report correctness
    """
    total_rows: int = Field(..., description="Total rows processed")
    successful: int = Field(..., description="Number of successful operations")
    failed: int = Field(..., description="Number of failed operations")
    results: List[BulkOperationRow] = Field(..., description="Per-row results")
    errors: List[str] = Field(default_factory=list, description="Global errors (file format, etc.)")
    
    @model_validator(mode='after')
    def validate_counts(self):
        """Validate that successful + failed = total_rows."""
        if self.successful + self.failed != self.total_rows:
            raise ValueError(
                f"Count mismatch: successful ({self.successful}) + "
                f"failed ({self.failed}) != total_rows ({self.total_rows})"
            )
        return self


# ============================================================================
# Bulk Campaign Schemas
# ============================================================================

class BulkCampaignRow(BaseModel):
    """
    Schema for a single campaign row in CSV.
    
    Requirements:
    - Req 2.1: Bulk campaign import
    - Req 10.4: Date format validation
    """
    name: str = Field(..., min_length=2, max_length=255)
    campaign_type: str = Field(..., description="Campaign type (ooh, construction, etc.)")
    start_date: str = Field(..., description="Start date in ISO 8601 format (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date in ISO 8601 format (YYYY-MM-DD)")
    address: Optional[str] = Field(None, max_length=500)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    location_name: Optional[str] = Field(None, max_length=255)


# ============================================================================
# Bulk Vendor Schemas
# ============================================================================

class BulkVendorRow(BaseModel):
    """
    Schema for a single vendor row in CSV.
    
    Requirements:
    - Req 3.1: Bulk vendor import
    - Req 3.4: Phone number format validation
    - Req 3.5: Email format validation
    """
    name: str = Field(..., min_length=2, max_length=255)
    phone_number: str = Field(..., description="Phone number in E.164 format (+1234567890)")
    email: Optional[str] = Field(None, description="Email address (optional)")
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v):
        """Validate E.164 phone number format."""
        if not v.startswith('+'):
            raise ValueError("Phone number must start with + (E.164 format)")
        if not v[1:].isdigit():
            raise ValueError("Phone number must contain only digits after +")
        if len(v) < 8 or len(v) > 16:
            raise ValueError("Phone number must be 8-16 characters (including +)")
        return v
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """Basic email format validation."""
        if v is None:
            return v
        if '@' not in v or '.' not in v.split('@')[1]:
            raise ValueError("Invalid email format")
        return v


# ============================================================================
# Bulk Assignment Schemas
# ============================================================================

class BulkAssignmentRow(BaseModel):
    """
    Schema for a single assignment row in CSV.
    
    Requirements:
    - Req 4.1: Bulk assignment import
    - Req 4.3, 4.4: Foreign key validation
    """
    campaign_code: str = Field(..., description="Campaign code")
    vendor_id: str = Field(..., description="Vendor ID (6 alphanumeric)")
    address: Optional[str] = Field(None, max_length=500)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    location_name: Optional[str] = Field(None, max_length=255)
    
    @field_validator('vendor_id')
    @classmethod
    def validate_vendor_id(cls, v):
        """Validate vendor ID format."""
        if len(v) != 6 or not v.isalnum():
            raise ValueError(f"Invalid vendor ID format: {v}. Must be 6 alphanumeric characters.")
        return v


# ============================================================================
# CSV Template Schemas
# ============================================================================

class CSVTemplateResponse(BaseModel):
    """Response containing CSV template."""
    filename: str
    content: str
    content_type: str = "text/csv"


# ============================================================================
# Query Schemas
# ============================================================================

class AssignmentListResponse(BaseModel):
    """Response for listing assignments."""
    assignments: List[VendorAssignmentResponse]
    total: int


class CampaignVendorsResponse(BaseModel):
    """Response for getting vendors assigned to a campaign."""
    campaign_id: UUID
    vendors: List[Dict[str, Any]]
    total: int


class VendorCampaignsResponse(BaseModel):
    """Response for getting campaigns assigned to a vendor."""
    vendor_id: str
    campaigns: List[Dict[str, Any]]
    total: int
