"""Photo Upload and Management API endpoints."""
import hashlib
import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_vendor
from app.core.config import settings
from app.models import Photo, SensorData, PhotoSignature, Campaign, Vendor, LocationProfile
from app.models.photo import VerificationStatus
from app.models.campaign_vendor_assignment import CampaignVendorAssignment
from app.schemas.photo import (
    SensorDataSchema, PhotoSignatureSchema, PhotoUploadResponse, PhotoResponse
)
from app.services.signature_verification import SignatureVerificationService
from app.services.location_profile_matcher import LocationProfileMatcher
from app.services.enhanced_verification import run_enhanced_verification, determine_status_from_verification
from app.core.storage import get_storage_service
from app.services.audit_logger import AuditLogger, AuditFlag
from app.services.quota_enforcer import get_quota_enforcer, QuotaExceededError
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/photos", tags=["photos"])
from app.core.deps import get_current_client
from app.models.client import Client

@router.get("")
async def list_photos(
    limit: int = 50,
    offset: int = 0,
    campaign_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client)
):
    """List photos for the current client."""
    from sqlalchemy import func
    query = select(Photo).where(Photo.tenant_id == client.tenant_id)
    if campaign_code:
        campaign = await db.execute(
            select(Campaign).where(Campaign.campaign_code == campaign_code, Campaign.tenant_id == client.tenant_id)
        )
        campaign = campaign.scalar_one_or_none()
        if campaign:
            query = query.where(Photo.campaign_id == campaign.campaign_id)
    # Join with SensorData, Campaign, Vendor for full details
    from app.models import SensorData as SD, Campaign as Cam, Vendor as Ven
    detail_query = (
        select(Photo, SD.gps_latitude, SD.gps_longitude, SD.gps_accuracy,
               Cam.name.label("campaign_name"), Cam.campaign_code,
               Ven.name.label("vendor_name"))
        .join(SD, SD.photo_id == Photo.photo_id, isouter=True)
        .join(Cam, Cam.campaign_id == Photo.campaign_id, isouter=True)
        .join(Ven, Ven.vendor_id == Photo.vendor_id, isouter=True)
        .where(Photo.tenant_id == client.tenant_id)
    )
    if campaign_code:
        campaign_result = await db.execute(
            select(Campaign).where(Campaign.campaign_code == campaign_code, Campaign.tenant_id == client.tenant_id)
        )
        campaign_obj = campaign_result.scalar_one_or_none()
        if campaign_obj:
            detail_query = detail_query.where(Photo.campaign_id == campaign_obj.campaign_id)
    detail_query = detail_query.order_by(Photo.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(detail_query)
    rows = result.all()
    storage = get_storage_service()
    return [
        {
            "photo_id": str(row[0].photo_id),
            "campaign_id": str(row[0].campaign_id),
            "campaign_name": row.campaign_name or "",
            "vendor_id": str(row[0].vendor_id) if row[0].vendor_id else None,
            "vendor_name": row.vendor_name or "",
            "photo_url": storage.get_photo_url(row[0].s3_key) if row[0].s3_key else None,
            "thumbnail_url": storage.get_thumbnail_url(row[0].s3_key) if row[0].s3_key else None,
            "status": row[0].verification_status.value if hasattr(row[0].verification_status, 'value') else str(row[0].verification_status),
            "verification_status": row[0].verification_status.value if hasattr(row[0].verification_status, 'value') else str(row[0].verification_status),
            "verification_confidence": row[0].verification_confidence or 0,
            "confidence_score": row[0].verification_confidence or 0,
            "gps_latitude": float(row.gps_latitude) if row.gps_latitude else 0,
            "gps_longitude": float(row.gps_longitude) if row.gps_longitude else 0,
            "gps_accuracy": float(row.gps_accuracy) if row.gps_accuracy else 0,
            "captured_at": row[0].capture_timestamp.isoformat() if row[0].capture_timestamp else (row[0].created_at.isoformat() if row[0].created_at else None),
            "created_at": row[0].created_at.isoformat() if row[0].created_at else None,
        }
        for row in rows
    ]

@router.get("/locations")
async def get_photo_locations(
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client)
):
    """Get photo locations for map view."""
    from app.models import SensorData as SD, Campaign as Cam, Vendor as Ven
    query = (
        select(Photo, SD.gps_latitude, SD.gps_longitude, SD.gps_accuracy,
               Cam.name.label("campaign_name"), Cam.campaign_code,
               Ven.name.label("vendor_name"))
        .join(SD, SD.photo_id == Photo.photo_id, isouter=True)
        .join(Cam, Cam.campaign_id == Photo.campaign_id, isouter=True)
        .join(Ven, Ven.vendor_id == Photo.vendor_id, isouter=True)
        .where(
            Photo.tenant_id == client.tenant_id,
            SD.gps_latitude.isnot(None),
            SD.gps_longitude.isnot(None)
        )
        .limit(500)
    )
    result = await db.execute(query)
    rows = result.all()
    storage = get_storage_service()
    features = []
    for row in rows:
        p = row[0]
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(row.gps_longitude), float(row.gps_latitude)]
            },
            "properties": {
                "photo_id": str(p.photo_id),
                "status": p.verification_status.value if hasattr(p.verification_status, 'value') else str(p.verification_status),
                "confidence": p.verification_confidence or 0,
                "flags": p.verification_flags or [],
                "campaign_name": row.campaign_name or "",
                "campaign_code": row.campaign_code or "",
                "vendor_name": row.vendor_name or "",
                "photo_url": storage.get_photo_url(p.s3_key) if p.s3_key else None,
                "thumbnail_url": storage.get_thumbnail_url(p.s3_key) if p.s3_key else None,
                "captured_at": p.capture_timestamp.isoformat() if p.capture_timestamp else (p.created_at.isoformat() if p.created_at else None),
            }
        })
    return {"type": "FeatureCollection", "features": features}




def validate_photo_file(file: UploadFile) -> bytes:
    """Validate photo file format and size."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required")
    file_ext = file.filename.lower().split('.')[-1]
    if file_ext not in settings.allowed_extensions_list:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid file format. Allowed: {', '.join(settings.allowed_extensions_list)}")
    file_bytes = file.file.read()
    if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB")
    if not (file_bytes[:2] == b'\xff\xd8' and file_bytes[-2:] == b'\xff\xd9'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JPEG file")
    return file_bytes


def calculate_photo_hash(photo_bytes: bytes) -> bytes:
    """Calculate SHA-256 hash of photo bytes."""
    return hashlib.sha256(photo_bytes).digest()


async def verify_campaign_and_vendor(campaign_code: str, vendor: Vendor, db: AsyncSession) -> Campaign:
    """Verify campaign exists and vendor is assigned to it."""
    result = await db.execute(select(Campaign).where(Campaign.campaign_code == campaign_code))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Campaign not found: {campaign_code}")
    from app.models.campaign import CampaignStatus
    if campaign.status != CampaignStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Campaign is not active: {campaign.status.value}")
    result = await db.execute(
        select(CampaignVendorAssignment).where(
            CampaignVendorAssignment.campaign_id == campaign.campaign_id,
            CampaignVendorAssignment.vendor_id == vendor.vendor_id
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vendor not assigned to this campaign")
    return campaign


@router.post("/upload", response_model=PhotoUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    photo: UploadFile = File(..., description="Photo file (JPEG, max 5MB)"),
    sensor_data: str = Form(..., description="JSON string of sensor data"),
    signature: str = Form(..., description="JSON string of photo signature"),
    campaign_code: str = Form(..., description="Campaign code"),
    capture_timestamp: str = Form(..., description="ISO format capture timestamp"),
    vendor: Vendor = Depends(get_current_vendor),
    db: AsyncSession = Depends(get_db)
):
    """Upload photo with sensor data and signature for verification.
    Task C: Enhanced verification with pressure/magnetic comparison, tremor flagging, confidence score.
    """
    # Validate photo file
    photo_bytes = validate_photo_file(photo)

    # Parse sensor data JSON
    try:
        sensor_data_dict = json.loads(sensor_data)
        sensor_data_obj = SensorDataSchema(**sensor_data_dict)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid sensor_data JSON")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid sensor_data format: {str(e)}")

    # Parse signature JSON
    try:
        signature_dict = json.loads(signature)
        signature_obj = PhotoSignatureSchema(**signature_dict)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature JSON")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid signature format: {str(e)}")

    # Parse capture timestamp
    try:
        capture_dt = datetime.fromisoformat(capture_timestamp.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid capture_timestamp format. Use ISO 8601.")

    # Verify campaign and vendor assignment
    campaign = await verify_campaign_and_vendor(campaign_code, vendor, db)

    # Check quotas (must be after campaign lookup to access campaign.client_id)
    enforcer = get_quota_enforcer(db)
    file_size_mb = len(photo_bytes) / (1024 * 1024)
    try:
        await enforcer.check_photo_quota(str(campaign.client_id))
        await enforcer.check_storage_quota(str(campaign.client_id), file_size_mb)
    except QuotaExceededError as e:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=e.to_dict())

    # Verify signature
    photo_hash = calculate_photo_hash(photo_bytes)
    signature_valid = False
    if vendor.public_key:
        try:
            import base64
            signature_bytes = base64.b64decode(signature_obj.signature)
            signature_valid = SignatureVerificationService.verify_signature(
                photo_hash=photo_hash, signature=signature_bytes,
                public_key=vendor.public_key, algorithm=signature_obj.algorithm
            )
        except Exception as e:
            logger.warning(f"Signature verification error: {str(e)}")
            signature_valid = False
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Vendor public key not registered.")

    # Get location profile if exists
    result = await db.execute(select(LocationProfile).where(LocationProfile.campaign_id == campaign.campaign_id))
    location_profile = result.scalar_one_or_none()

    # Match location profile if exists
    location_match_result = None
    if location_profile:
        matcher = LocationProfileMatcher()
        captured_data = {
            'latitude': sensor_data_obj.gps.latitude,
            'longitude': sensor_data_obj.gps.longitude,
        }
        if sensor_data_obj.wifi_networks:
            captured_data['wifi_bssids'] = [w.bssid for w in sensor_data_obj.wifi_networks]
        if sensor_data_obj.cell_towers:
            captured_data['cell_tower_ids'] = [str(c.cell_id) for c in sensor_data_obj.cell_towers]
        if sensor_data_obj.environmental:
            if sensor_data_obj.environmental.barometer_pressure:
                captured_data['pressure'] = sensor_data_obj.environmental.barometer_pressure
            if sensor_data_obj.environmental.ambient_light_lux:
                captured_data['light_level'] = sensor_data_obj.environmental.ambient_light_lux
        location_match_result = matcher.match_location(captured_data, location_profile)

    # Task C: Enhanced verification (includes delivery window check)
    verification_result = run_enhanced_verification(
        signature_valid=signature_valid,
        location_match_result=location_match_result,
        sensor_data=sensor_data_obj,
        location_profile=location_profile,
        campaign=campaign,
        capture_timestamp=capture_dt,
    )

    # Determine status from enhanced verification
    status_str = determine_status_from_verification(verification_result)
    verification_status = VerificationStatus(status_str)

    # Generate photo ID
    photo_id = uuid.uuid4()

    # Upload to S3
    try:
        photo_s3_key, photo_url, thumbnail_s3_key, thumbnail_url = get_storage_service().upload_photo_with_thumbnail(
            photo_bytes=photo_bytes, campaign_id=str(campaign.campaign_id), photo_id=str(photo_id)
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to upload photo: {str(e)}")

    # Create Photo record
    photo_record = Photo(
        photo_id=photo_id, campaign_id=campaign.campaign_id, vendor_id=vendor.vendor_id,
        tenant_id=vendor.tenant_id, capture_timestamp=capture_dt, upload_timestamp=datetime.utcnow(),
        s3_key=photo_s3_key, thumbnail_s3_key=thumbnail_s3_key,
        verification_status=verification_status, signature_valid=signature_valid,
        location_match_score=location_match_result['match_score'] if location_match_result else None,
        distance_from_expected=location_match_result['distance_meters'] if location_match_result else None,
        verification_confidence=verification_result.confidence_score,
        verification_flags=verification_result.flags if verification_result.flags else None,
        created_at=datetime.utcnow()
    )
    db.add(photo_record)
    await db.flush()

    # Create SensorData record
    sensor_record = SensorData(
        sensor_data_id=uuid.uuid4(), photo_id=photo_id,
        gps_latitude=sensor_data_obj.gps.latitude, gps_longitude=sensor_data_obj.gps.longitude,
        gps_altitude=sensor_data_obj.gps.altitude, gps_accuracy=sensor_data_obj.gps.accuracy,
        gps_provider=sensor_data_obj.gps.provider, gps_satellite_count=sensor_data_obj.gps.satellite_count,
        wifi_networks=[w.model_dump() for w in sensor_data_obj.wifi_networks] if sensor_data_obj.wifi_networks else None,
        cell_towers=[c.model_dump() for c in sensor_data_obj.cell_towers] if sensor_data_obj.cell_towers else None,
        location_hash=sensor_data_obj.location_hash, confidence_score=sensor_data_obj.confidence_score,
        schema_version=sensor_data_obj.schema_version, created_at=datetime.utcnow()
    )
    if sensor_data_obj.environmental:
        env = sensor_data_obj.environmental
        sensor_record.barometer_pressure = env.barometer_pressure
        sensor_record.barometer_altitude = env.barometer_altitude
        sensor_record.ambient_light_lux = env.ambient_light_lux
        sensor_record.magnetic_field_x = env.magnetic_field_x
        sensor_record.magnetic_field_y = env.magnetic_field_y
        sensor_record.magnetic_field_z = env.magnetic_field_z
        sensor_record.magnetic_field_magnitude = env.magnetic_field_magnitude
        sensor_record.hand_tremor_frequency = env.hand_tremor_frequency
        sensor_record.hand_tremor_is_human = env.hand_tremor_is_human
        sensor_record.hand_tremor_confidence = env.hand_tremor_confidence
    db.add(sensor_record)

    # Create PhotoSignature record
    signature_record = PhotoSignature(
        signature_id=uuid.uuid4(), photo_id=photo_id,
        signature_data=signature_obj.signature, algorithm=signature_obj.algorithm,
        device_id=signature_obj.device_id, timestamp=signature_obj.timestamp,
        location_hash=signature_obj.location_hash, created_at=datetime.utcnow()
    )
    db.add(signature_record)

    await db.commit()

    # Increment usage counters
    try:
        await enforcer.increment_photo_usage(str(campaign.client_id))
        await enforcer.increment_storage_usage(str(campaign.client_id), file_size_mb)
    except Exception as e:
        logger.error(f"Failed to increment usage counters: {str(e)}")

    # Audit logging
    try:
        audit_logger = AuditLogger(db)
        audit_flags = []
        if location_match_result and location_match_result.get('match_score', 100) < 80:
            audit_flags.append(AuditFlag.LOCATION_MISMATCH.value)
        if sensor_data_obj.gps.accuracy and sensor_data_obj.gps.accuracy > 50:
            audit_flags.append(AuditFlag.LOW_GPS_ACCURACY.value)
        # Add enhanced verification flags to audit
        audit_flags.extend(verification_result.flags)
        device_info = {'device_id': signature_obj.device_id, 'vendor_id': vendor.vendor_id}
        audit_sensor_data = {
            'gps': {'latitude': sensor_data_obj.gps.latitude, 'longitude': sensor_data_obj.gps.longitude,
                     'altitude': sensor_data_obj.gps.altitude, 'accuracy': sensor_data_obj.gps.accuracy,
                     'provider': sensor_data_obj.gps.provider, 'satellite_count': sensor_data_obj.gps.satellite_count},
            'wifi_networks': [w.model_dump() for w in sensor_data_obj.wifi_networks] if sensor_data_obj.wifi_networks else [],
            'cell_towers': [c.model_dump() for c in sensor_data_obj.cell_towers] if sensor_data_obj.cell_towers else [],
            'location_hash': sensor_data_obj.location_hash, 'confidence_score': sensor_data_obj.confidence_score
        }
        if sensor_data_obj.environmental:
            audit_sensor_data['environmental'] = sensor_data_obj.environmental.model_dump()
        audit_signature_data = {
            'signature': signature_obj.signature, 'algorithm': signature_obj.algorithm,
            'timestamp': signature_obj.timestamp, 'location_hash': signature_obj.location_hash, 'valid': signature_valid
        }
        await audit_logger.log_photo_capture(
            photo_id=str(photo_id), vendor_id=vendor.vendor_id, campaign_code=campaign_code,
            sensor_data=audit_sensor_data, signature=audit_signature_data,
            device_info=device_info, flags=audit_flags if audit_flags else None
        )
    except Exception as e:
        logger.error(f"Audit logging failed (non-critical): {str(e)}")

    return PhotoUploadResponse(
        photo_id=photo_id, verification_status=verification_status.value,
        signature_valid=signature_valid,
        location_match_score=location_match_result['match_score'] if location_match_result else None,
        distance_from_expected=location_match_result['distance_meters'] if location_match_result else None,
        verification_confidence=verification_result.confidence_score,
        verification_flags=verification_result.flags if verification_result.flags else None,
        s3_url=photo_url, thumbnail_url=thumbnail_url,
        message=f"Photo uploaded and {verification_status.value}"
    )


@router.get("/{photo_id}", response_model=PhotoResponse)
async def get_photo(
    photo_id: uuid.UUID,
    vendor: Vendor = Depends(get_current_vendor),
    db: AsyncSession = Depends(get_db)
):
    """Get photo details by ID."""
    result = await db.execute(select(Photo).where(Photo.photo_id == photo_id))
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    if photo.vendor_id != vendor.vendor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this photo")
    return photo
