"""
Campaign-Vendor Assignment API endpoints.

Requirements:
- Req 1.1: Create campaign-vendor assignments
- Req 1.2: Prevent duplicate assignments
- Req 1.3: Delete assignments
- Req 1.4: Query assignments by campaign
- Req 1.5: Query assignments by vendor
- Req 1.6: Foreign key validation
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, and_
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.deps import get_current_active_client
from app.models.client import Client
from app.models.campaign import Campaign
from app.models.vendor import Vendor
from app.models.campaign_vendor_assignment import CampaignVendorAssignment
from app.schemas.assignment import (
    VendorAssignmentCreate,
    VendorAssignmentResponse,
    VendorAssignmentBatchResponse,
    AssignmentListResponse,
    CampaignVendorsResponse,
    VendorCampaignsResponse,
    LocationAssignment
)
from app.services.geocoding_service import get_geocoding_service, GeocodingError
from app.core.error_codes import ErrorCode
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["assignments"])


@router.post(
    "/campaigns/{campaign_id}/vendors",
    response_model=VendorAssignmentBatchResponse,
    status_code=status.HTTP_201_CREATED
)
async def assign_vendors_to_campaign(
    campaign_id: UUID,
    assignment_data: VendorAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_active_client)
):
    """
    Assign one or more vendors to a campaign with optional location.
    
    Requirements:
    - Req 1.1: Create campaign-vendor assignments
    - Req 1.2: Prevent duplicate assignments
    - Req 1.6: Foreign key validation
    - Property 1: Assignment creation correctness
    - Property 2: Duplicate assignment prevention
    """
    # Verify campaign exists and belongs to client
    result = await db.execute(
        select(Campaign).where(
            and_(
                Campaign.campaign_id == campaign_id,
                Campaign.client_id == current_client.client_id
            )
        )
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found or access denied"
        )
    
    # Process location data if provided
    location_data = {}
    if assignment_data.location:
        location_data = {
            "assignment_address": assignment_data.location.address,
            "assignment_latitude": assignment_data.location.latitude,
            "assignment_longitude": assignment_data.location.longitude,
            "assignment_location_name": assignment_data.location.name
        }
        
        # If address provided but no coordinates, geocode it
        if assignment_data.location.address and not assignment_data.location.latitude:
            try:
                geocoding_service = get_geocoding_service()
                geocode_result = await geocoding_service.geocode_address(
                    assignment_data.location.address
                )
                location_data["assignment_latitude"] = geocode_result.latitude
                location_data["assignment_longitude"] = geocode_result.longitude
                location_data["assignment_address"] = geocode_result.formatted_address
            except GeocodingError as e:
                # Geocoding failure is non-fatal, continue with provided address
                logger.warning(f"Failed to geocode address: {e}")
                pass
    
    assignments = []
    errors = []
    
    for vendor_id in assignment_data.vendor_ids:
        try:
            # Verify vendor exists and belongs to client
            result = await db.execute(
                select(Vendor).where(
                    and_(
                        Vendor.vendor_id == vendor_id,
                        Vendor.created_by_client_id == current_client.client_id
                    )
                )
            )
            vendor = result.scalar_one_or_none()
            
            if not vendor:
                errors.append(f"Vendor {vendor_id} not found or access denied")
                continue
            
            # Check for existing assignment (duplicate prevention)
            result = await db.execute(
                select(CampaignVendorAssignment).where(
                    and_(
                        CampaignVendorAssignment.campaign_id == campaign_id,
                        CampaignVendorAssignment.vendor_id == vendor_id
                    )
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                errors.append(f"Vendor {vendor_id} already assigned to campaign")
                continue
            
            # Create assignment
            assignment = CampaignVendorAssignment(
                campaign_id=campaign_id,
                vendor_id=vendor_id,
                **location_data
            )
            
            db.add(assignment)
            await db.flush()  # Get the assignment_id
            await db.refresh(assignment)
            
            # Build response
            location_response = None
            if location_data:
                location_response = LocationAssignment(
                    address=assignment.assignment_address,
                    latitude=assignment.assignment_latitude,
                    longitude=assignment.assignment_longitude,
                    name=assignment.assignment_location_name
                )
            
            assignments.append(
                VendorAssignmentResponse(
                    assignment_id=assignment.assignment_id,
                    campaign_id=assignment.campaign_id,
                    vendor_id=assignment.vendor_id,
                    assigned_at=assignment.assigned_at,
                    location=location_response,
                    created_at=assignment.created_at,
                    updated_at=assignment.updated_at
                )
            )
            
        except Exception as e:
            errors.append(f"Error assigning vendor {vendor_id}: {str(e)}")
    
    # Commit all successful assignments with rollback safety
    if assignments:
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Database integrity error during assignment: {e}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "A constraint violation occurred. Some assignments may already exist.",
                    "code": ErrorCode.DB_CONSTRAINT_VIOLATION
                }
            )
    
    return VendorAssignmentBatchResponse(
        assignments=assignments,
        errors=errors
    )


@router.delete(
    "/campaigns/{campaign_id}/vendors/{vendor_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def unassign_vendor_from_campaign(
    campaign_id: UUID,
    vendor_id: str,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_active_client)
):
    """
    Remove a vendor assignment from a campaign.
    
    Requirements:
    - Req 1.3: Delete assignments
    - Property 3: Assignment deletion round-trip
    """
    # Verify campaign belongs to client
    result = await db.execute(
        select(Campaign).where(
            and_(
                Campaign.campaign_id == campaign_id,
                Campaign.client_id == current_client.client_id
            )
        )
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found or access denied"
        )
    
    # Find and delete assignment
    result = await db.execute(
        select(CampaignVendorAssignment).where(
            and_(
                CampaignVendorAssignment.campaign_id == campaign_id,
                CampaignVendorAssignment.vendor_id == vendor_id
            )
        )
    )
    assignment = result.scalar_one_or_none()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment not found for campaign {campaign_id} and vendor {vendor_id}"
        )
    
    try:
        await db.delete(assignment)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting assignment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to delete assignment", "code": ErrorCode.INTERNAL_ERROR}
        )


@router.get(
    "/campaigns/{campaign_id}/vendors",
    response_model=CampaignVendorsResponse
)
async def get_campaign_vendors(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_active_client)
):
    """
    Get all vendors assigned to a campaign.
    
    Requirements:
    - Req 1.4: Query assignments by campaign
    - Property 4: Assignment query correctness
    """
    # Verify campaign belongs to client
    result = await db.execute(
        select(Campaign).where(
            and_(
                Campaign.campaign_id == campaign_id,
                Campaign.client_id == current_client.client_id
            )
        )
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found or access denied"
        )
    
    # Get all assignments for this campaign
    result = await db.execute(
        select(CampaignVendorAssignment, Vendor)
        .join(Vendor, CampaignVendorAssignment.vendor_id == Vendor.vendor_id)
        .where(CampaignVendorAssignment.campaign_id == campaign_id)
    )
    assignments = result.all()
    
    vendors = []
    for assignment, vendor in assignments:
        vendor_data = {
            "vendor_id": vendor.vendor_id,
            "name": vendor.name,
            "phone_number": vendor.phone_number,
            "email": vendor.email,
            "status": vendor.status,
            "assignment_id": assignment.assignment_id,
            "assigned_at": assignment.assigned_at.isoformat(),
            "location": None
        }
        
        # Add location if present
        if assignment.assignment_address or assignment.assignment_latitude:
            vendor_data["location"] = {
                "address": assignment.assignment_address,
                "latitude": assignment.assignment_latitude,
                "longitude": assignment.assignment_longitude,
                "name": assignment.assignment_location_name
            }
        
        vendors.append(vendor_data)
    
    return CampaignVendorsResponse(
        campaign_id=campaign_id,
        vendors=vendors,
        total=len(vendors)
    )


@router.get(
    "/vendors/{vendor_id}/campaigns",
    response_model=VendorCampaignsResponse
)
async def get_vendor_campaigns(
    vendor_id: str,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_active_client)
):
    """
    Get all campaigns assigned to a vendor.
    
    Requirements:
    - Req 1.5: Query assignments by vendor
    - Property 4: Assignment query correctness
    """
    # Verify vendor belongs to client
    result = await db.execute(
        select(Vendor).where(
            and_(
                Vendor.vendor_id == vendor_id,
                Vendor.created_by_client_id == current_client.client_id
            )
        )
    )
    vendor = result.scalar_one_or_none()
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor {vendor_id} not found or access denied"
        )
    
    # Get all assignments for this vendor
    result = await db.execute(
        select(CampaignVendorAssignment, Campaign)
        .join(Campaign, CampaignVendorAssignment.campaign_id == Campaign.campaign_id)
        .where(CampaignVendorAssignment.vendor_id == vendor_id)
    )
    assignments = result.all()
    
    campaigns = []
    for assignment, campaign in assignments:
        campaign_data = {
            "campaign_id": str(campaign.campaign_id),
            "name": campaign.name,
            "campaign_code": campaign.campaign_code,
            "campaign_type": campaign.campaign_type,
            "status": campaign.status,
            "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
            "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
            "assignment_id": assignment.assignment_id,
            "assigned_at": assignment.assigned_at.isoformat(),
            "location": None
        }
        
        # Add location if present
        if assignment.assignment_address or assignment.assignment_latitude:
            campaign_data["location"] = {
                "address": assignment.assignment_address,
                "latitude": assignment.assignment_latitude,
                "longitude": assignment.assignment_longitude,
                "name": assignment.assignment_location_name
            }
        
        campaigns.append(campaign_data)
    
    return VendorCampaignsResponse(
        vendor_id=vendor_id,
        campaigns=campaigns,
        total=len(campaigns)
    )
