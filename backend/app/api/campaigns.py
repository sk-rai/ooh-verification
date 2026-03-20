"""Campaign Management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from datetime import datetime
from typing import Optional
from uuid import UUID
from app.core.database import get_db
from app.core.deps import get_current_active_client
from app.core.security import generate_campaign_code
from app.core.sms import sms_service
from app.models import Client, Campaign, LocationProfile, CampaignVendorAssignment, Vendor
from app.models.campaign import CampaignStatus, CampaignType
from app.schemas.campaign import (CampaignCreate, CampaignUpdate, CampaignResponse, CampaignListResponse, VendorAssignmentCreate, VendorAssignmentResponse)
from app.services.quota_enforcer import get_quota_enforcer, QuotaExceededError
from app.services.elevation_service import get_pressure_range
from app.services.magnetic_field_service import get_magnetic_field_range
import logging
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])
@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(data: CampaignCreate, client: Client = Depends(get_current_active_client), db: AsyncSession = Depends(get_db)):
    """Create a new campaign with optional location profile. Task A1: pressure auto-pop. Task A2: magnetic auto-pop."""
    enforcer = get_quota_enforcer(db)
    try:
        await enforcer.check_campaign_quota(str(client.client_id))
    except QuotaExceededError as e:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=e.to_dict())
    max_attempts = 10
    campaign_code = None
    for _ in range(max_attempts):
        candidate_code = generate_campaign_code()
        result = await db.execute(select(Campaign).where(Campaign.campaign_code == candidate_code))
        existing = result.scalar_one_or_none()
        if not existing:
            campaign_code = candidate_code
            break
    if not campaign_code:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate unique campaign code")
    campaign = Campaign(campaign_code=campaign_code, tenant_id=client.tenant_id, name=data.name, campaign_type=data.campaign_type.value if hasattr(data.campaign_type, "value") else data.campaign_type, client_id=client.client_id, start_date=data.start_date, end_date=data.end_date)
    db.add(campaign)
    await db.flush()
    if data.location_profile:
        lp = data.location_profile
        has_coords = lp.expected_latitude is not None and lp.expected_longitude is not None
        pressure_min = lp.expected_pressure_min
        pressure_max = lp.expected_pressure_max
        if pressure_min is None and pressure_max is None and has_coords:
            try:
                pr = await get_pressure_range(lp.expected_latitude, lp.expected_longitude)
                if pr:
                    pressure_min, pressure_max = pr
                    logger.info(f"Auto-populated pressure for {campaign_code}: [{pressure_min}, {pressure_max}] hPa")
            except Exception as e:
                logger.warning(f"Failed to auto-populate pressure: {e}")
        magnetic_min = lp.expected_magnetic_min
        magnetic_max = lp.expected_magnetic_max
        if magnetic_min is None and magnetic_max is None and has_coords:
            try:
                mr = await get_magnetic_field_range(lp.expected_latitude, lp.expected_longitude)
                if mr:
                    magnetic_min, magnetic_max = mr
                    logger.info(f"Auto-populated magnetic for {campaign_code}: [{magnetic_min}, {magnetic_max}] uT")
            except Exception as e:
                logger.warning(f"Failed to auto-populate magnetic field: {e}")
        loc_profile = LocationProfile(campaign_id=campaign.campaign_id, expected_latitude=lp.expected_latitude, expected_longitude=lp.expected_longitude, tolerance_meters=lp.tolerance_meters, expected_wifi_bssids=lp.expected_wifi_bssids, expected_cell_tower_ids=lp.expected_cell_tower_ids, expected_pressure_min=pressure_min, expected_pressure_max=pressure_max, expected_light_min=lp.expected_light_min, expected_light_max=lp.expected_light_max, expected_magnetic_min=magnetic_min, expected_magnetic_max=magnetic_max)
        db.add(loc_profile)
    await db.commit()
    try:
        await enforcer.increment_campaign_usage(str(client.client_id))
    except Exception as e:
        logger.error(f"Failed to increment campaign usage: {str(e)}")
    result = await db.execute(select(Campaign).where(Campaign.campaign_id == campaign.campaign_id).options(selectinload(Campaign.location_profile)))
    campaign = result.scalar_one()
    return campaign
@router.get("", response_model=CampaignListResponse)
async def list_campaigns(status_filter: Optional[str] = Query(None), campaign_type: Optional[str] = Query(None), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), client: Client = Depends(get_current_active_client), db: AsyncSession = Depends(get_db)):
    """List all campaigns for the authenticated client."""
    query = select(Campaign).where(Campaign.client_id == client.client_id).options(selectinload(Campaign.location_profile))
    if status_filter:
        try:
            status_enum = CampaignStatus(status_filter.lower())
            query = query.where(Campaign.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status: {status_filter}")
    if campaign_type:
        try:
            type_enum = CampaignType(campaign_type.lower())
            query = query.where(Campaign.campaign_type == type_enum)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid campaign type: {campaign_type}")
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    query = query.order_by(Campaign.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    campaigns = result.scalars().all()
    return CampaignListResponse(campaigns=campaigns, total=total)
@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: UUID, client: Client = Depends(get_current_active_client), db: AsyncSession = Depends(get_db)):
    """Get campaign details by ID."""
    result = await db.execute(select(Campaign).where(Campaign.campaign_id == campaign_id, Campaign.client_id == client.client_id).options(selectinload(Campaign.location_profile)))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign
@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(campaign_id: UUID, data: CampaignUpdate, client: Client = Depends(get_current_active_client), db: AsyncSession = Depends(get_db)):
    """Update campaign information."""
    result = await db.execute(select(Campaign).where(Campaign.campaign_id == campaign_id, Campaign.client_id == client.client_id).options(selectinload(Campaign.location_profile)))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if data.name is not None:
        campaign.name = data.name
    if data.status is not None:
        campaign.status = CampaignStatus(data.status)
    if data.end_date is not None:
        if data.end_date <= campaign.start_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_date must be after start_date")
        campaign.end_date = data.end_date
    campaign.updated_at = datetime.utcnow()
    await db.commit()
    result = await db.execute(select(Campaign).where(Campaign.campaign_id == campaign.campaign_id).options(selectinload(Campaign.location_profile)))
    campaign = result.scalar_one()
    return campaign
@router.post("/{campaign_id}/vendors", response_model=list[VendorAssignmentResponse], status_code=status.HTTP_201_CREATED)
async def assign_vendors_to_campaign(campaign_id: UUID, data: VendorAssignmentCreate, client: Client = Depends(get_current_active_client), db: AsyncSession = Depends(get_db)):
    """Assign vendors to a campaign and send SMS notifications."""
    result = await db.execute(select(Campaign).where(Campaign.campaign_id == campaign_id, Campaign.client_id == client.client_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    assignments = []
    errors = []
    for vendor_id in data.vendor_ids:
        vendor_result = await db.execute(select(Vendor).where(Vendor.vendor_id == vendor_id, Vendor.created_by_client_id == client.client_id))
        vendor = vendor_result.scalar_one_or_none()
        if not vendor:
            errors.append(f"Vendor {vendor_id} not found")
            continue
        existing_result = await db.execute(select(CampaignVendorAssignment).where(CampaignVendorAssignment.campaign_id == campaign_id, CampaignVendorAssignment.vendor_id == vendor_id))
        existing = existing_result.scalar_one_or_none()
        if existing:
            errors.append(f"Vendor {vendor_id} already assigned")
            continue
        assignment = CampaignVendorAssignment(campaign_id=campaign_id, vendor_id=vendor_id)
        db.add(assignment)
        assignments.append(assignment)
        await sms_service.send_campaign_assignment_sms(phone_number=vendor.phone_number, vendor_name=vendor.name, campaign_name=campaign.name, campaign_code=campaign.campaign_code)
    if not assignments and errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to assign vendors: {'; '.join(errors)}")
    await db.commit()
    for assignment in assignments:
        await db.refresh(assignment)
    return assignments
@router.delete("/{campaign_id}/vendors/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_vendor_from_campaign(campaign_id: UUID, vendor_id: str, client: Client = Depends(get_current_active_client), db: AsyncSession = Depends(get_db)):
    """Remove a vendor assignment from a campaign."""
    result = await db.execute(select(Campaign).where(Campaign.campaign_id == campaign_id, Campaign.client_id == client.client_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    assignment_result = await db.execute(select(CampaignVendorAssignment).where(CampaignVendorAssignment.campaign_id == campaign_id, CampaignVendorAssignment.vendor_id == vendor_id))
    assignment = assignment_result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor assignment not found")
    await db.delete(assignment)
    await db.commit()
    return None
