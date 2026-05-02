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
from app.models.vendor_client_association import VendorClientAssociation, AssociationStatus
from app.models import Client, Campaign, LocationProfile, CampaignVendorAssignment, Vendor
from app.models.campaign import CampaignStatus, CampaignType
from app.schemas.campaign import (CampaignCreate, CampaignUpdate, CampaignResponse, CampaignListResponse, VendorAssignmentCreate, VendorAssignmentResponse)
from app.services.quota_enforcer import get_quota_enforcer, QuotaExceededError
from app.services.elevation_service import get_pressure_range
from app.services.magnetic_field_service import get_magnetic_field_range
from app.services.geocoding_service import get_geocoding_service, GeocodingError
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
    # Multi-location support: accept locations array or single location_profile
    all_locations = []
    if data.locations:
        all_locations = data.locations
    elif data.location_profile:
        lp = data.location_profile
        all_locations = [{
            "expected_latitude": lp.expected_latitude,
            "expected_longitude": lp.expected_longitude,
            "tolerance_meters": lp.tolerance_meters,
            "address": getattr(lp, "address", None),
            "expected_wifi_bssids": lp.expected_wifi_bssids,
            "expected_cell_tower_ids": lp.expected_cell_tower_ids,
            "expected_pressure_min": lp.expected_pressure_min,
            "expected_pressure_max": lp.expected_pressure_max,
            "expected_light_min": lp.expected_light_min,
            "expected_light_max": lp.expected_light_max,
            "expected_magnetic_min": lp.expected_magnetic_min,
            "expected_magnetic_max": lp.expected_magnetic_max,
            "delivery_window_start": getattr(lp, "delivery_window_start", None),
            "delivery_window_end": getattr(lp, "delivery_window_end", None),
        }]

    # Tier-based location limits
    from app.models.subscription import Subscription
    sub_result = await db.execute(select(Subscription).where(Subscription.client_id == client.client_id))
    sub = sub_result.scalar_one_or_none()
    tier_str = "free"
    if sub and sub.tier:
        tier_str = sub.tier.value if hasattr(sub.tier, 'value') else str(sub.tier)
    tier_limits = {"free": 5, "pro": 500, "enterprise": 99999}
    max_locations = tier_limits.get(tier_str.lower(), 5)
    logger.info(f"Location limit check: tier={tier_str}, locations={len(all_locations)}, max={max_locations}")
    if len(all_locations) > max_locations:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=f"Your {tier_str} plan allows {max_locations} locations per campaign. Upgrade to add more.")

    geocoding_service = get_geocoding_service()
    for loc_data in all_locations:
        loc_lat = loc_data.get('expected_latitude')
        loc_lon = loc_data.get('expected_longitude')
        loc_address = loc_data.get('address')
        resolved_address = None
        tolerance = loc_data.get('tolerance_meters', 100)
        has_coords = loc_lat is not None and loc_lon is not None
        has_address = loc_address and str(loc_address).strip()
        if has_address and not has_coords:
            try:
                geo_result = await geocoding_service.geocode_address(str(loc_address))
                if geo_result:
                    loc_lat = geo_result.latitude
                    loc_lon = geo_result.longitude
                    resolved_address = geo_result.formatted_address
                    has_coords = True
            except Exception as e:
                logger.warning(f"Geocoding failed for location: {e}")
        elif has_coords and not has_address:
            try:
                geo_result = await geocoding_service.reverse_geocode(float(loc_lat), float(loc_lon))
                if geo_result:
                    resolved_address = geo_result.formatted_address
            except Exception:
                pass
        elif has_address and has_coords:
            resolved_address = str(loc_address)
        if not has_coords:
            continue  # Skip locations without coordinates
        # Auto-populate pressure and magnetic ranges
        pressure_min = loc_data.get('expected_pressure_min')
        pressure_max = loc_data.get('expected_pressure_max')
        if pressure_min is None and pressure_max is None:
            try:
                pr = await get_pressure_range(float(loc_lat), float(loc_lon))
                if pr: pressure_min, pressure_max = pr
            except Exception: pass
        magnetic_min = loc_data.get('expected_magnetic_min')
        magnetic_max = loc_data.get('expected_magnetic_max')
        if magnetic_min is None and magnetic_max is None:
            try:
                mr = await get_magnetic_field_range(float(loc_lat), float(loc_lon))
                if mr: magnetic_min, magnetic_max = mr
            except Exception: pass
        if data.campaign_type in ('delivery', 'DELIVERY') and tolerance == 50.0:
            tolerance = 150.0
        loc_profile = LocationProfile(campaign_id=campaign.campaign_id, expected_latitude=float(loc_lat), expected_longitude=float(loc_lon), tolerance_meters=float(tolerance), expected_pressure_min=pressure_min, expected_pressure_max=pressure_max, expected_magnetic_min=magnetic_min, expected_magnetic_max=magnetic_max, resolved_address=resolved_address, expected_wifi_bssids=loc_data.get('expected_wifi_bssids'), expected_cell_tower_ids=loc_data.get('expected_cell_tower_ids'), expected_light_min=loc_data.get('expected_light_min'), expected_light_max=loc_data.get('expected_light_max'), delivery_window_start=loc_data.get('delivery_window_start'), delivery_window_end=loc_data.get('delivery_window_end'))
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
    result = await db.execute(select(Campaign).where(Campaign.campaign_id == campaign_id, Campaign.client_id == client.client_id))
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
    # Handle location updates
    if data.locations is not None:
        from app.models.location_profile import LocationProfile
        from app.services.geocoding_service import get_geocoding_service
        from app.services.elevation_service import get_pressure_range
        from app.services.magnetic_field_service import get_magnetic_field_range
        from app.models.subscription import Subscription
        # Tier-based location limit check
        sub_result = await db.execute(select(Subscription).where(Subscription.client_id == client.client_id))
        sub = sub_result.scalar_one_or_none()
        tier_str = "free"
        if sub and sub.tier:
            tier_str = sub.tier.value if hasattr(sub.tier, 'value') else str(sub.tier)
        tier_limits = {"free": 5, "pro": 500, "enterprise": 99999}
        max_locations = tier_limits.get(tier_str.lower(), 5)
        if len(data.locations) > max_locations:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=f"Your {tier_str} plan allows {max_locations} locations per campaign.")
        # Phase 1: Raw SQL DELETE (bypasses identity map)
        from sqlalchemy import delete as sql_delete
        await db.execute(sql_delete(LocationProfile).where(LocationProfile.campaign_id == campaign.campaign_id))
        await db.flush()  # CRITICAL: flush DELETE before INSERT
        logger.info(f"Deleted old locations for campaign {campaign.campaign_id}, adding {len(data.locations)} new")
        # Create new locations
        geocoding_service = get_geocoding_service()
        for loc_data in data.locations:
            loc_lat = loc_data.get('expected_latitude')
            loc_lon = loc_data.get('expected_longitude')
            loc_address = loc_data.get('address')
            resolved_address = None
            tolerance = loc_data.get('tolerance_meters', 100)
            has_coords = loc_lat is not None and loc_lon is not None
            has_address = loc_address and str(loc_address).strip()
            if has_address and not has_coords:
                try:
                    geo_result = await geocoding_service.geocode_address(str(loc_address))
                    if geo_result:
                        loc_lat, loc_lon = geo_result.latitude, geo_result.longitude
                        resolved_address = geo_result.formatted_address
                        has_coords = True
                except Exception as e:
                    logger.warning(f"Geocoding failed: {e}")
            elif has_coords and not has_address:
                try:
                    geo_result = await geocoding_service.reverse_geocode(float(loc_lat), float(loc_lon))
                    if geo_result: resolved_address = geo_result.formatted_address
                except Exception: pass
            elif has_address and has_coords:
                resolved_address = str(loc_address)
            if not has_coords:
                continue
            pressure_min = pressure_max = magnetic_min = magnetic_max = None
            try:
                pr = await get_pressure_range(float(loc_lat), float(loc_lon))
                if pr: pressure_min, pressure_max = pr
            except Exception: pass
            try:
                mr = await get_magnetic_field_range(float(loc_lat), float(loc_lon))
                if mr: magnetic_min, magnetic_max = mr
            except Exception: pass
            db.add(LocationProfile(
                campaign_id=campaign.campaign_id,
                expected_latitude=float(loc_lat), expected_longitude=float(loc_lon),
                tolerance_meters=float(tolerance),
                expected_pressure_min=pressure_min, expected_pressure_max=pressure_max,
                expected_magnetic_min=magnetic_min, expected_magnetic_max=magnetic_max,
                resolved_address=resolved_address,
            ))

    campaign.updated_at = datetime.utcnow()
    await db.commit()
    # Re-fetch campaign with fresh locations
    from app.models.location_profile import LocationProfile as LP2
    result = await db.execute(select(Campaign).where(Campaign.campaign_id == campaign.campaign_id))
    campaign = result.scalar_one()
    lp_result = await db.execute(select(LP2).where(LP2.campaign_id == campaign.campaign_id))
    campaign.location_profile = lp_result.scalars().all()
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
        vendor_result = await db.execute(
            select(Vendor).join(
                VendorClientAssociation, Vendor.vendor_id == VendorClientAssociation.vendor_id
            ).where(
                Vendor.vendor_id == vendor_id,
                VendorClientAssociation.client_id == client.client_id,
                VendorClientAssociation.status == AssociationStatus.ACTIVE
            )
        )
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


@router.get("/{campaign_id}/photos")
async def get_campaign_photos(
    campaign_id: UUID,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """Get photos for a specific campaign."""
    from app.models import Photo, SensorData as SD, Vendor as Ven
    from app.core.storage import get_storage_service

    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign_id,
            Campaign.tenant_id == client.tenant_id
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    query = (
        select(Photo, SD.gps_latitude, SD.gps_longitude, SD.gps_accuracy,
               Ven.name.label("vendor_name"))
        .join(SD, SD.photo_id == Photo.photo_id, isouter=True)
        .join(Ven, Ven.vendor_id == Photo.vendor_id, isouter=True)
        .where(Photo.campaign_id == campaign_id, Photo.tenant_id == client.tenant_id)
        .order_by(Photo.created_at.desc())
        .offset(offset).limit(limit)
    )
    result = await db.execute(query)
    rows = result.all()

    storage = get_storage_service()
    return [
        {
            "photo_id": str(row[0].photo_id),
            "campaign_id": str(row[0].campaign_id),
            "vendor_id": str(row[0].vendor_id) if row[0].vendor_id else None,
            "vendor_name": row.vendor_name or "",
            "photo_url": storage.get_photo_url(row[0].s3_key) if row[0].s3_key else None,
            "thumbnail_url": storage.get_thumbnail_url(row[0].s3_key) if row[0].s3_key else None,
            "status": row[0].verification_status.value if hasattr(row[0].verification_status, 'value') else str(row[0].verification_status),
            "verification_status": row[0].verification_status.value if hasattr(row[0].verification_status, 'value') else str(row[0].verification_status),
            "verification_confidence": row[0].verification_confidence or 0,
            "gps_latitude": float(row.gps_latitude) if row.gps_latitude else 0,
            "gps_longitude": float(row.gps_longitude) if row.gps_longitude else 0,
            "gps_accuracy": float(row.gps_accuracy) if row.gps_accuracy else 0,
            "captured_at": row[0].capture_timestamp.isoformat() if row[0].capture_timestamp else (row[0].created_at.isoformat() if row[0].created_at else None),
            "created_at": row[0].created_at.isoformat() if row[0].created_at else None,
            "verification_flags": row[0].verification_flags or [],
        }
        for row in rows
    ]

