"""Vendor-facing campaign endpoints.
Provides endpoints for vendors to view their assigned campaigns."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_active_vendor
from app.models import Vendor, Campaign
from app.models.campaign_vendor_assignment import CampaignVendorAssignment

router = APIRouter(prefix="/api/vendors/me", tags=["vendor-campaigns"])


@router.get("/campaigns")
async def get_my_campaigns(
    vendor: Vendor = Depends(get_current_active_vendor),
    db: AsyncSession = Depends(get_db)
):
    """Get all campaigns assigned to the current vendor.
    
    Returns campaigns with assignment details.
    Requires vendor JWT token.
    """
    # Get assignments with campaign data
    result = await db.execute(
        select(CampaignVendorAssignment)
        .where(CampaignVendorAssignment.vendor_id == vendor.vendor_id)
        .options(
            selectinload(CampaignVendorAssignment.campaign)
            .selectinload(Campaign.location_profile)
        )
    )
    assignments = result.scalars().all()

    campaigns = []
    for assignment in assignments:
        campaign = assignment.campaign
        if campaign:
            campaigns.append({
                "campaign_id": str(campaign.campaign_id),
                "campaign_code": campaign.campaign_code,
                "name": campaign.name,
                "campaign_type": campaign.campaign_type.value if hasattr(campaign.campaign_type, 'value') else campaign.campaign_type,
                "status": campaign.status.value if hasattr(campaign.status, 'value') else campaign.status,
                "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
                "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
                "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
                "assignment_address": assignment.assignment_address,
                "assignment_latitude": assignment.assignment_latitude,
                "assignment_longitude": assignment.assignment_longitude,
                "assignment_location_name": assignment.assignment_location_name,
                "location_profile": {
                    "expected_latitude": campaign.location_profile.expected_latitude,
                    "expected_longitude": campaign.location_profile.expected_longitude,
                    "tolerance_meters": campaign.location_profile.tolerance_meters,
                } if campaign.location_profile else None,
            })

    return {"campaigns": campaigns, "total": len(campaigns)}
