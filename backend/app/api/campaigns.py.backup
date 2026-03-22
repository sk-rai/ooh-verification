"""
Campaign Management API endpoints.

Provides campaign CRUD operations, location profile management, and vendor assignments.
"""
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
from app.schemas.campaign import (
    CampaignCreate, CampaignUpdate, CampaignResponse, CampaignListResponse,
    VendorAssignmentCreate, VendorAssignmentResponse
)

from app.services.quota_enforcer import get_quota_enforcer, QuotaExceededError

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate,
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new campaign with optional location profile.

    Requirements:
        - Req 1.1: Campaign creation
        - Req 1.2: Campaign code validation
        - Req 1.4: Campaign expiration dates
        - Req 7.1-7.4: Location profile creation
        - Req 12.1: Campaign code format
        - Req 11.4: Quota enforcement
    """
    # Check campaign quota
    enforcer = get_quota_enforcer(db)
    try:
        await enforcer.check_campaign_quota(str(client.client_id))
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=e.to_dict()
        )
    
    # Generate unique campaign code
    max_attempts = 10
    campaign_code = None

    for _ in range(max_attempts):
        candidate_code = generate_campaign_code()

        # Check if code already exists
        result = await db.execute(
            select(Campaign).where(Campaign.campaign_code == candidate_code)
        )
        existing = result.scalar_one_or_none()

        if not existing:
            campaign_code = candidate_code
            break

    if not campaign_code:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate unique campaign code"
        )

    # Create campaign
    campaign = Campaign(
        campaign_code=campaign_code,
        name=data.name,
        campaign_type=CampaignType(data.campaign_type),
        client_id=client.client_id,
        start_date=data.start_date,
        end_date=data.end_date,
        status=CampaignStatus.ACTIVE
    )

    db.add(campaign)
    await db.flush()  # Flush to get campaign_id for location profile

    # Create location profile if provided
    if data.location_profile:
        location_profile = LocationProfile(
            campaign_id=campaign.campaign_id,
            expected_latitude=data.location_profile.expected_latitude,
            expected_longitude=data.location_profile.expected_longitude,
            tolerance_meters=data.location_profile.tolerance_meters,
            expected_wifi_bssids=data.location_profile.expected_wifi_bssids,
            expected_cell_tower_ids=data.location_profile.expected_cell_tower_ids,
            expected_pressure_min=data.location_profile.expected_pressure_min,
            expected_pressure_max=data.location_profile.expected_pressure_max,
            expected_light_min=data.location_profile.expected_light_min,
            expected_light_max=data.location_profile.expected_light_max
        )
        db.add(location_profile)

    await db.commit()
    
    # Increment campaign usage counter (Req 11.3: Usage tracking)
    try:
        await enforcer.increment_campaign_usage(str(client.client_id))
    except Exception as e:
        # Log error but don't fail since campaign is already created
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to increment campaign usage: {str(e)}")

    # Reload campaign with location_profile relationship
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign.campaign_id
        ).options(selectinload(Campaign.location_profile))
    )
    campaign = result.scalar_one()

    return campaign
@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)





@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    status_filter: Optional[str] = Query(None, description="Filter by status (active/completed/cancelled)"),
    campaign_type: Optional[str] = Query(None, description="Filter by campaign type"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    List all campaigns for the authenticated client.

    Supports filtering by status and campaign type, with pagination.

    Requirements:
        - Req 1.2: Campaign listing
        - Authorization: Clients can only see their own campaigns
    """
    # Build query with eager loading of location_profile
    query = select(Campaign).where(
        Campaign.client_id == client.client_id
    ).options(selectinload(Campaign.location_profile))

    # Apply status filter if provided
    if status_filter:
        try:
            status_enum = CampaignStatus(status_filter.lower())
            query = query.where(Campaign.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}. Must be 'active', 'completed', or 'cancelled'"
            )

    # Apply campaign type filter if provided
    if campaign_type:
        try:
            type_enum = CampaignType(campaign_type.lower())
            query = query.where(Campaign.campaign_type == type_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid campaign type: {campaign_type}"
            )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination and ordering
    query = query.order_by(Campaign.created_at.desc()).offset(skip).limit(limit)

    # Execute query
    result = await db.execute(query)
    campaigns = result.scalars().all()

    return CampaignListResponse(campaigns=campaigns, total=total)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: UUID,
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Get campaign details by ID.

    Requirements:
        - Req 1.3: Campaign details retrieval
        - Authorization: Clients can only access their own campaigns
    """
    # Get campaign with location profile
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign_id,
            Campaign.client_id == client.client_id
        ).options(selectinload(Campaign.location_profile))
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    return campaign


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: UUID,
    data: CampaignUpdate,
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Update campaign information.

    Requirements:
        - Req 1.4: Campaign updates
        - Authorization: Clients can only update their own campaigns
    """
    # Get campaign
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign_id,
            Campaign.client_id == client.client_id
        ).options(selectinload(Campaign.location_profile))
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    # Update fields if provided
    if data.name is not None:
        campaign.name = data.name
    if data.status is not None:
        campaign.status = CampaignStatus(data.status)
    if data.end_date is not None:
        # Validate end_date is after start_date
        if data.end_date <= campaign.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date must be after start_date"
            )
        campaign.end_date = data.end_date

    campaign.updated_at = datetime.utcnow()

    await db.commit()
    # Reload campaign with location_profile relationship
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign.campaign_id
        ).options(selectinload(Campaign.location_profile))
    )
    campaign = result.scalar_one()

    return campaign


@router.post("/{campaign_id}/vendors", response_model=list[VendorAssignmentResponse], status_code=status.HTTP_201_CREATED)
async def assign_vendors_to_campaign(
    campaign_id: UUID,
    data: VendorAssignmentCreate,
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Assign vendors to a campaign and send SMS notifications.

    Requirements:
        - Req 1.1: Vendor assignment to campaigns
        - Req 1.3: SMS notifications to assigned vendors
    """
    # Verify campaign exists and belongs to client
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign_id,
            Campaign.client_id == client.client_id
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    assignments = []
    errors = []

    for vendor_id in data.vendor_ids:
        # Verify vendor exists and belongs to client
        vendor_result = await db.execute(
            select(Vendor).where(
                Vendor.vendor_id == vendor_id,
                Vendor.created_by_client_id == client.client_id
            )
        )
        vendor = vendor_result.scalar_one_or_none()

        if not vendor:
            errors.append(f"Vendor {vendor_id} not found")
            continue

        # Check if assignment already exists
        existing_result = await db.execute(
            select(CampaignVendorAssignment).where(
                CampaignVendorAssignment.campaign_id == campaign_id,
                CampaignVendorAssignment.vendor_id == vendor_id
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            errors.append(f"Vendor {vendor_id} already assigned to campaign")
            continue

        # Create assignment
        assignment = CampaignVendorAssignment(
            campaign_id=campaign_id,
            vendor_id=vendor_id
        )
        db.add(assignment)
        assignments.append(assignment)

        # Send SMS notification to vendor
        await sms_service.send_campaign_assignment_sms(
            phone_number=vendor.phone_number,
            vendor_name=vendor.name,
            campaign_name=campaign.name,
            campaign_code=campaign.campaign_code
        )

    if not assignments and errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to assign vendors: {'; '.join(errors)}"
        )

    await db.commit()

    # Refresh assignments to get all fields
    for assignment in assignments:
        await db.refresh(assignment)

    return assignments


@router.delete("/{campaign_id}/vendors/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_vendor_from_campaign(
    campaign_id: UUID,
    vendor_id: str,
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a vendor assignment from a campaign.

    Requirements:
        - Req 1.3: Vendor assignment management
        - Authorization: Clients can only manage their own campaigns
    """
    # Verify campaign exists and belongs to client
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign_id,
            Campaign.client_id == client.client_id
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    # Get assignment
    assignment_result = await db.execute(
        select(CampaignVendorAssignment).where(
            CampaignVendorAssignment.campaign_id == campaign_id,
            CampaignVendorAssignment.vendor_id == vendor_id
        )
    )
    assignment = assignment_result.scalar_one_or_none()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor assignment not found"
        )

    await db.delete(assignment)
    await db.commit()

    return None


