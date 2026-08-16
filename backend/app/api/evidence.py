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
            # Try multiple field name patterns (Android sends various formats)
            latitude = (
                parsed_sensor_data.get("gps_latitude") or
                parsed_sensor_data.get("latitude") or
                parsed_sensor_data.get("lat") or
                (parsed_sensor_data.get("gps", {}) or {}).get("latitude") or
                (parsed_sensor_data.get("location", {}) or {}).get("latitude")
            )
            longitude = (
                parsed_sensor_data.get("gps_longitude") or
                parsed_sensor_data.get("longitude") or
                parsed_sensor_data.get("lon") or
                parsed_sensor_data.get("lng") or
                (parsed_sensor_data.get("gps", {}) or {}).get("longitude") or
                (parsed_sensor_data.get("location", {}) or {}).get("longitude")
            )
            accuracy = (
                parsed_sensor_data.get("gps_accuracy") or
                parsed_sensor_data.get("accuracy") or
                (parsed_sensor_data.get("gps", {}) or {}).get("accuracy") or
                (parsed_sensor_data.get("location", {}) or {}).get("accuracy")
            )
            # Convert to float if string
            if latitude and isinstance(latitude, str):
                latitude = float(latitude)
            if longitude and isinstance(longitude, str):
                longitude = float(longitude)
            if accuracy and isinstance(accuracy, str):
                accuracy = float(accuracy)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"Error parsing sensor_data: {e}")

    # Fallback: extract GPS from gps_track first point (for video/voice without sensor_data)
    if (not latitude or not longitude) and gps_track:
        try:
            track_points = json.loads(gps_track) if isinstance(gps_track, str) else gps_track
            if isinstance(track_points, list) and len(track_points) > 0:
                first_point = track_points[0]
                latitude = latitude or first_point.get("lat") or first_point.get("latitude")
                longitude = longitude or first_point.get("lon") or first_point.get("lng") or first_point.get("longitude")
                accuracy = accuracy or first_point.get("accuracy")
                if latitude and isinstance(latitude, str):
                    latitude = float(latitude)
                if longitude and isinstance(longitude, str):
                    longitude = float(longitude)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

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
                # Generate thumbnail for video (Cloudinary: use .jpg extension for video frame)
                if evidence_type == "video":
                    # Cloudinary video thumbnail: add transformation + change extension to .jpg
                    base_url = file_url.rsplit(".", 1)[0]  # remove .mp4/.mov extension
                    thumbnail_url = base_url.replace("/upload/", "/upload/w_200,h_200,c_fill,so_1/") + ".jpg"
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
            from app.services.location_profile_matcher import LocationProfileMatcher
            from app.models.location_profile import LocationProfile

            # Get location profiles for campaign (if campaign exists)
            location_profile = None
            location_match_result = None

            if resolved_campaign_id:
                lp_result = await db.execute(
                    select(LocationProfile).where(LocationProfile.campaign_id == resolved_campaign_id)
                )
                profiles = lp_result.scalars().all()
                if profiles:
                    location_profile = profiles[0]  # Use first profile
                    # Run location matching
                    if latitude and longitude:
                        matcher = LocationProfileMatcher()
                        captured_data = {
                            "latitude": latitude,
                            "longitude": longitude,
                        }
                        # Add optional sensor data if available
                        if parsed_sensor_data:
                            captured_data.update({
                                "wifi_bssids": parsed_sensor_data.get("wifi_bssids"),
                                "cell_tower_ids": parsed_sensor_data.get("cell_tower_ids"),
                                "pressure": parsed_sensor_data.get("barometric_pressure"),
                                "light_level": parsed_sensor_data.get("light_level"),
                            })
                        location_match_result = matcher.match_location(
                            captured_data=captured_data,
                            location_profile=location_profile
                        )

            # Determine signature validity
            signature_valid = signature is not None and len(signature) > 0

            # Run verification
            result = run_enhanced_verification(
                signature_valid=signature_valid,
                location_match_result=location_match_result,
                sensor_data=parsed_sensor_data,
                location_profile=location_profile,
            )
            verification_confidence = result.confidence_score
            verification_flags = result.flags
            # Determine status from confidence + flags
            if "LOCATION_FAR_FROM_EXPECTED" in verification_flags or "SIGNATURE_INVALID" in verification_flags:
                verification_status = "rejected"
            elif verification_confidence >= 0.65:
                verification_status = "verified"
            elif verification_confidence >= 0.40:
                verification_status = "flagged"
            else:
                verification_status = "rejected"
        except Exception as e:
            import traceback
            logger.error(f"Verification failed for evidence {evidence.evidence_id}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            print(f"❌ Verification error: {e}")
            print(f"   location_match_result: {location_match_result}")
            print(f"   latitude: {latitude}, longitude: {longitude}")
            print(f"   location_profile: {location_profile}")
            print(traceback.format_exc())
            verification_status = "pending"
            verification_confidence = 0.0

    elif evidence_type == "video":
        # Video verification: check location if campaign assigned, then signature/track
        from app.services.location_profile_matcher import LocationProfileMatcher
        from app.models.location_profile import LocationProfile

        video_location_ok = True
        if resolved_campaign_id and latitude and longitude:
            lp_result = await db.execute(
                select(LocationProfile).where(LocationProfile.campaign_id == resolved_campaign_id)
            )
            profiles = lp_result.scalars().all()
            if profiles:
                matcher = LocationProfileMatcher()
                match_result = matcher.match_location(
                    captured_data={"latitude": latitude, "longitude": longitude},
                    location_profile=profiles[0]
                )
                if match_result:
                    distance = match_result.get("distance_meters", 0)
                    if distance > 1000:
                        verification_flags.append("LOCATION_FAR_FROM_EXPECTED")
                        video_location_ok = False
                    elif distance > 200:
                        verification_flags.append("LOCATION_MODERATE_DEVIATION")

        if not video_location_ok:
            verification_status = "rejected"
            verification_confidence = 0.3
        elif signature and gps_track:
            verification_status = "verified"
            verification_confidence = 0.75
        else:
            verification_status = "flagged"
            verification_confidence = 0.5
            if not signature:
                verification_flags.append("MISSING_SIGNATURE")
            if not gps_track:
                verification_flags.append("MISSING_GPS_TRACK")

    elif evidence_type == "voice_note":
        # Voice notes: check location if campaign assigned, otherwise verified
        from app.services.location_profile_matcher import LocationProfileMatcher
        from app.models.location_profile import LocationProfile

        voice_location_ok = True
        if resolved_campaign_id and latitude and longitude:
            lp_result = await db.execute(
                select(LocationProfile).where(LocationProfile.campaign_id == resolved_campaign_id)
            )
            profiles = lp_result.scalars().all()
            if profiles:
                matcher = LocationProfileMatcher()
                match_result = matcher.match_location(
                    captured_data={"latitude": latitude, "longitude": longitude},
                    location_profile=profiles[0]
                )
                if match_result:
                    distance = match_result.get("distance_meters", 0)
                    if distance > 1000:
                        verification_flags.append("LOCATION_FAR_FROM_EXPECTED")
                        voice_location_ok = False
                    elif distance > 200:
                        verification_flags.append("LOCATION_MODERATE_DEVIATION")

        if not voice_location_ok:
            verification_status = "rejected"
            verification_confidence = 0.3
        else:
            verification_status = "verified"
            verification_confidence = 1.0

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




@router.get("/distance")
async def get_evidence_distance(
    id1: str,
    id2: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Calculate haversine distance between two evidence items."""
    import math
    tenant_id = get_current_tenant(request)

    result1 = await db.execute(
        select(Evidence).where(Evidence.evidence_id == id1, Evidence.tenant_id == tenant_id)
    )
    result2 = await db.execute(
        select(Evidence).where(Evidence.evidence_id == id2, Evidence.tenant_id == tenant_id)
    )
    ev1 = result1.scalar_one_or_none()
    ev2 = result2.scalar_one_or_none()

    if not ev1 or not ev2:
        raise HTTPException(status_code=404, detail="Evidence not found")

    lat1, lon1 = ev1.latitude or 0, ev1.longitude or 0
    lat2, lon2 = ev2.latitude or 0, ev2.longitude or 0

    if not lat1 or not lon1 or not lat2 or not lon2:
        return {"distance_meters": None, "error": "GPS coordinates missing on one or both items"}

    # Haversine
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    distance = 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

    # Time difference
    time_diff = None
    speed_kmh = None
    if ev1.created_at and ev2.created_at:
        time_diff = abs((ev2.created_at - ev1.created_at).total_seconds())
        if time_diff > 0:
            speed_kmh = round((distance / 1000) / (time_diff / 3600), 1)

    return {
        "distance_meters": round(distance, 1),
        "distance_km": round(distance / 1000, 2),
        "time_difference_seconds": time_diff,
        "speed_kmh": speed_kmh,
        "evidence_1": {"id": str(ev1.evidence_id), "lat": lat1, "lon": lon1, "time": ev1.created_at.isoformat() if ev1.created_at else None},
        "evidence_2": {"id": str(ev2.evidence_id), "lat": lat2, "lon": lon2, "time": ev2.created_at.isoformat() if ev2.created_at else None},
        "flags": ["IMPOSSIBLE_SPEED"] if speed_kmh and speed_kmh > 150 else [],
    }


@router.get("/route-analysis")
async def get_route_analysis(
    campaign_id: Optional[str] = None,
    vendor_id: Optional[str] = None,
    date: Optional[str] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze route for a vendor on a given day — sequential distances, gaps, speed.
    Returns ordered captures with distance from previous.
    """
    import math
    from datetime import datetime as dt, timedelta
    tenant_id = get_current_tenant(request)

    query = select(Evidence).where(Evidence.tenant_id == tenant_id)
    if campaign_id:
        query = query.where(Evidence.campaign_id == campaign_id)
    if vendor_id:
        query = query.where(Evidence.vendor_id == vendor_id)
    if date:
        try:
            day_start = dt.fromisoformat(date)
            day_end = day_start + timedelta(days=1)
            query = query.where(Evidence.created_at >= day_start, Evidence.created_at < day_end)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

    query = query.order_by(Evidence.created_at)
    result = await db.execute(query)
    items = result.scalars().all()

    # Also get from photos table
    from app.models import Photo, SensorData
    photo_query = (
        select(Photo, SensorData.gps_latitude, SensorData.gps_longitude)
        .join(SensorData, SensorData.photo_id == Photo.photo_id, isouter=True)
        .where(Photo.tenant_id == tenant_id)
    )
    if campaign_id:
        photo_query = photo_query.where(Photo.campaign_id == campaign_id)
    if vendor_id:
        photo_query = photo_query.where(Photo.vendor_id == vendor_id)
    if date:
        day_start = dt.fromisoformat(date)
        day_end = day_start + timedelta(days=1)
        photo_query = photo_query.where(Photo.created_at >= day_start, Photo.created_at < day_end)
    photo_query = photo_query.order_by(Photo.created_at)
    photo_result = await db.execute(photo_query)
    photo_rows = photo_result.all()

    # Combine into unified points list
    points = []
    for ev in items:
        if ev.latitude and ev.longitude:
            points.append({
                "id": str(ev.evidence_id),
                "lat": ev.latitude,
                "lon": ev.longitude,
                "time": ev.created_at.isoformat() if ev.created_at else None,
                "type": ev.evidence_type,
                "status": ev.verification_status,
            })
    for row in photo_rows:
        lat = float(row.gps_latitude) if row.gps_latitude else None
        lon = float(row.gps_longitude) if row.gps_longitude else None
        if lat and lon:
            points.append({
                "id": str(row[0].photo_id),
                "lat": lat,
                "lon": lon,
                "time": row[0].created_at.isoformat() if row[0].created_at else None,
                "type": "photo",
                "status": row[0].verification_status.value if hasattr(row[0].verification_status, 'value') else str(row[0].verification_status),
            })

    # Sort by time
    points.sort(key=lambda p: p["time"] or "")

    # Calculate sequential distances
    R = 6371000
    total_distance = 0.0
    max_gap = 0.0
    flags = []
    for i in range(len(points)):
        if i == 0:
            points[i]["distance_from_prev_m"] = 0
            points[i]["distance_from_prev_km"] = 0
            continue
        lat1, lon1 = points[i-1]["lat"], points[i-1]["lon"]
        lat2, lon2 = points[i]["lat"], points[i]["lon"]
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
        dist = 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))
        points[i]["distance_from_prev_m"] = round(dist, 1)
        points[i]["distance_from_prev_km"] = round(dist / 1000, 2)
        total_distance += dist
        if dist > max_gap:
            max_gap = dist

        # Speed check
        if points[i]["time"] and points[i-1]["time"]:
            from datetime import datetime as dtt
            t1 = dtt.fromisoformat(points[i-1]["time"])
            t2 = dtt.fromisoformat(points[i]["time"])
            secs = (t2 - t1).total_seconds()
            if secs > 0:
                speed = (dist / 1000) / (secs / 3600)
                points[i]["speed_kmh"] = round(speed, 1)
                if speed > 150:
                    flags.append({"point": i, "flag": "IMPOSSIBLE_SPEED", "speed_kmh": round(speed, 1)})

    # Gap detection (>2km between consecutive points)
    for i in range(1, len(points)):
        if points[i].get("distance_from_prev_m", 0) > 2000:
            flags.append({"point": i, "flag": "LARGE_GAP", "distance_km": points[i]["distance_from_prev_km"]})

    return {
        "total_points": len(points),
        "total_distance_km": round(total_distance / 1000, 2),
        "max_gap_km": round(max_gap / 1000, 2),
        "flags": flags,
        "points": points,
    }


@router.post("/fix-video-thumbnails")
async def fix_video_thumbnails(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Fix video thumbnail URLs: change .mp4 extension to .jpg for Cloudinary frame extraction."""
    from sqlalchemy import text
    tenant_id = get_current_tenant(request)

    result = await db.execute(text("""
        UPDATE evidence
        SET thumbnail_url = REPLACE(
            REPLACE(thumbnail_url, '.mp4', '.jpg'),
            '.mov', '.jpg'
        )
        WHERE evidence_type = 'video'
          AND thumbnail_url IS NOT NULL
          AND (thumbnail_url LIKE '%.mp4' OR thumbnail_url LIKE '%.mov')
          AND tenant_id = :tid
    """), {"tid": tenant_id})
    await db.commit()
    return {"status": "Fixed video thumbnails", "rows_updated": result.rowcount}
