"""
Evidence Upload API — unified endpoint for photo, video, voice note, and text note uploads.

Replaces /api/photos/upload for new app versions while maintaining backward compatibility.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime
from uuid import UUID
import hashlib
import json
import logging

from app.core.database import get_db
from app.core.deps import get_current_active_vendor
from app.models.vendor import Vendor
from app.models.campaign import Campaign
from app.models.evidence import Evidence, GpsTrack, EvidenceType, EvidenceStatus
from app.middleware.tenant_context import get_current_tenant
from app.core.storage import get_storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    request: Request,
    file: Optional[UploadFile] = File(None),
    evidence_type: str = Form(...),
    campaign_id: Optional[str] = Form(None),
    campaign_code: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    text_content: Optional[str] = Form(None),
    sensor_data: Optional[str] = Form(None),
    signature: Optional[str] = Form(None),
    gps_track: Optional[str] = Form(None),
    capture_timestamp: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_active_vendor),
):
    """
    Upload evidence (photo, video, voice note, or text note).

    - file: Required for photo/video/voice_note. Not needed for text_note.
    - evidence_type: "photo", "video", "voice_note", "text_note"
    - campaign_id: Optional UUID. If null, this is a quick capture.
    - campaign_code: Alternative to campaign_id (backend resolves).
    - category: Optional category tag.
    - text_content: For text_note type = the note body. For others = optional notes.
    - sensor_data: JSON string with GPS, WiFi, cell tower, pressure, magnetic data.
    - signature: JSON string with device cryptographic signature.
    - gps_track: JSON array for video [{lat, lon, accuracy, timestamp_ms}, ...]
    - capture_timestamp: ISO 8601 string.
    """
    tenant_id = get_current_tenant(request)

    # Validate evidence type
    valid_types = ["photo", "video", "voice_note", "text_note"]
    if evidence_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid evidence_type. Must be one of: {', '.join(valid_types)}"
        )

    # File required for non-text types
    if evidence_type != "text_note" and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is required for evidence_type '{evidence_type}'"
        )

    # Text content required for text_note
    if evidence_type == "text_note" and not text_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="text_content is required for text_note type"
        )

    # Resolve campaign (optional)
    resolved_campaign_id = None
    if campaign_id:
        try:
            resolved_campaign_id = UUID(campaign_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid campaign_id UUID")
    elif campaign_code:
        result = await db.execute(
            select(Campaign).where(Campaign.campaign_code == campaign_code)
        )
        campaign = result.scalar_one_or_none()
        if campaign:
            resolved_campaign_id = campaign.campaign_id

    # Parse sensor data
    parsed_sensor_data = None
    latitude = None
    longitude = None
    accuracy = None
    if sensor_data:
        try:
            parsed_sensor_data = json.loads(sensor_data)
            latitude = parsed_sensor_data.get("gps_latitude") or parsed_sensor_data.get("latitude")
            longitude = parsed_sensor_data.get("gps_longitude") or parsed_sensor_data.get("longitude")
            accuracy = parsed_sensor_data.get("gps_accuracy") or parsed_sensor_data.get("accuracy")
        except json.JSONDecodeError:
            logger.warning("Invalid sensor_data JSON, ignoring")

    # Parse capture timestamp
    parsed_timestamp = None
    if capture_timestamp:
        try:
            parsed_timestamp = datetime.fromisoformat(capture_timestamp.replace("Z", "+00:00"))
        except ValueError:
            parsed_timestamp = datetime.utcnow()
    else:
        parsed_timestamp = datetime.utcnow()

    # Upload file to storage
    file_key = None
    file_url = None
    thumbnail_key = None
    thumbnail_url = None
    file_size = None
    mime_type = None
    file_hash = None

    if file:
        file_bytes = await file.read()
        file_size = len(file_bytes)
        mime_type = file.content_type

        # Validate file size (50MB max)
        if file_size > 50 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File too large. Maximum 50MB allowed."
            )

        # Compute file hash
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Upload to storage
        try:
            storage = get_storage_service()
            evidence_id_str = str(__import__("uuid").uuid4())

            if evidence_type == "photo":
                # Use existing photo upload (Cloudinary with thumbnail)
                file_key, file_url, thumbnail_key, thumbnail_url = storage.upload_photo_with_thumbnail(
                    file_bytes,
                    str(resolved_campaign_id or "quick-capture"),
                    evidence_id_str
                )
            else:
                # For video/voice: upload as raw file
                # TODO: Switch to S3 for large files. For now use Cloudinary raw upload.
                import cloudinary.uploader
                upload_result = cloudinary.uploader.upload(
                    file_bytes,
                    public_id=f"trustcapture/evidence/{evidence_id_str}",
                    resource_type="auto",
                    overwrite=True,
                )
                file_key = upload_result["public_id"]
                file_url = upload_result["secure_url"]
                # Generate thumbnail for video
                if evidence_type == "video":
                    thumbnail_url = file_url.replace("/upload/", "/upload/w_200,h_200,c_fill,so_1/")
                    thumbnail_key = file_key
        except Exception as e:
            logger.error(f"Storage upload failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload file to storage"
            )

    # Determine duration (from sensor_data or metadata)
    duration = None
    if parsed_sensor_data:
        duration = parsed_sensor_data.get("duration_seconds")

    # Create evidence record
    evidence = Evidence(
        tenant_id=tenant_id,
        campaign_id=resolved_campaign_id,
        vendor_id=current_vendor.vendor_id,
        evidence_type=evidence_type,
        category=category,
        file_key=file_key,
        file_url=file_url,
        thumbnail_key=thumbnail_key,
        thumbnail_url=thumbnail_url,
        file_size_bytes=file_size,
        mime_type=mime_type,
        duration_seconds=duration,
        text_content=text_content,
        capture_timestamp=parsed_timestamp,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        verification_status=EvidenceStatus.PENDING.value,
        device_signature=signature,
        file_hash=file_hash,
        sensor_data=parsed_sensor_data,
    )
    db.add(evidence)
    await db.flush()
    await db.refresh(evidence)

    # Store GPS track if provided (for video)
    if gps_track:
        try:
            track_points = json.loads(gps_track)
            if isinstance(track_points, list) and len(track_points) > 0:
                # Calculate duration and distance
                track_duration = None
                track_distance = None
                if len(track_points) >= 2:
                    first_ts = track_points[0].get("timestamp_ms", 0)
                    last_ts = track_points[-1].get("timestamp_ms", 0)
                    if first_ts and last_ts:
                        track_duration = (last_ts - first_ts) / 1000.0

                gps_track_record = GpsTrack(
                    evidence_id=evidence.evidence_id,
                    points=track_points,
                    duration_seconds=track_duration,
                    total_distance_meters=track_distance,
                )
                db.add(gps_track_record)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Invalid gps_track JSON: {e}")

    # Run verification
    verification_status = EvidenceStatus.PENDING.value
    verification_confidence = None
    verification_flags = []

    if evidence_type == "photo" and parsed_sensor_data:
        # Run the existing photo verification pipeline
        try:
            from app.services.enhanced_verification import run_enhanced_verification
            from app.models.location_profile import LocationProfile

            # Get location profiles for campaign (if campaign exists)
            location_profiles = []
            if resolved_campaign_id:
                lp_result = await db.execute(
                    select(LocationProfile).where(LocationProfile.campaign_id == resolved_campaign_id)
                )
                location_profiles = lp_result.scalars().all()

            # Run verification
            result = await run_enhanced_verification(
                sensor_data=parsed_sensor_data,
                location_profiles=location_profiles,
                signature_data=json.loads(signature) if signature else None,
            )
            verification_status = result.get("status", "pending")
            verification_confidence = result.get("confidence", 0)
            verification_flags = result.get("flags", [])
        except Exception as e:
            logger.error(f"Verification failed for evidence {evidence.evidence_id}: {e}")
            verification_status = "pending"

    elif evidence_type == "video":
        # Video verification: async (mark as pending, process in background)
        # For now: basic checks (device signature present, GPS track present)
        if signature and gps_track:
            verification_status = "verified"
            verification_confidence = 0.75  # Base confidence for video with track + signature
        else:
            verification_status = "flagged"
            verification_confidence = 0.5
            if not signature:
                verification_flags.append("MISSING_SIGNATURE")
            if not gps_track:
                verification_flags.append("MISSING_GPS_TRACK")

    elif evidence_type == "voice_note":
        # Voice note: verify device signature + GPS presence
        if signature and latitude and longitude:
            verification_status = "verified"
            verification_confidence = 0.70
        else:
            verification_status = "flagged"
            verification_confidence = 0.5

    elif evidence_type == "text_note":
        # Text notes: no verification (informational)
        verification_status = "verified"
        verification_confidence = 1.0

    # Update evidence with verification result
    evidence.verification_status = verification_status
    evidence.verification_confidence = verification_confidence
    evidence.verification_flags = verification_flags

    await db.commit()
    await db.refresh(evidence)

    return {
        "evidence_id": str(evidence.evidence_id),
        "evidence_type": evidence.evidence_type,
        "verification_status": evidence.verification_status,
        "verification_confidence": evidence.verification_confidence,
        "verification_flags": evidence.verification_flags,
        "file_url": evidence.file_url,
        "thumbnail_url": evidence.thumbnail_url,
        "message": "Evidence uploaded successfully",
    }


@router.get("/{evidence_id}")
async def get_evidence(
    evidence_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get evidence details by ID."""
    tenant_id = get_current_tenant(request)

    result = await db.execute(
        select(Evidence).where(
            Evidence.evidence_id == evidence_id,
            Evidence.tenant_id == tenant_id,
        )
    )
    evidence = result.scalar_one_or_none()

    if not evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")

    return {
        "evidence_id": str(evidence.evidence_id),
        "evidence_type": evidence.evidence_type,
        "campaign_id": str(evidence.campaign_id) if evidence.campaign_id else None,
        "vendor_id": evidence.vendor_id,
        "category": evidence.category,
        "text_content": evidence.text_content,
        "file_url": evidence.file_url,
        "thumbnail_url": evidence.thumbnail_url,
        "file_size_bytes": evidence.file_size_bytes,
        "duration_seconds": evidence.duration_seconds,
        "capture_timestamp": evidence.capture_timestamp.isoformat() if evidence.capture_timestamp else None,
        "latitude": evidence.latitude,
        "longitude": evidence.longitude,
        "accuracy": evidence.accuracy,
        "verification_status": evidence.verification_status,
        "verification_confidence": evidence.verification_confidence,
        "verification_flags": evidence.verification_flags,
        "created_at": evidence.created_at.isoformat(),
    }
