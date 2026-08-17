"""
3rd Party Verification API — stateless photo verification via API key.

POST /api/v1/verify — send photo + GPS, get confidence score back.
No vendor/campaign context needed.
"""
import hashlib
import math
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.api_key import APIKey

import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["verification-api"])


async def validate_api_key(
    authorization: str = Header(..., description="Bearer tc_live_xxxx or tc_test_xxxx"),
    db: AsyncSession = Depends(get_db),
) -> APIKey:
    """Validate API key from Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format. Use: Bearer tc_live_xxxx")

    raw_key = authorization[7:]  # Remove "Bearer "

    if len(raw_key) < 16:
        raise HTTPException(status_code=401, detail="Invalid API key format")

    # Extract prefix for lookup
    key_prefix = raw_key[:12]

    # Find key by prefix
    result = await db.execute(
        select(APIKey).where(APIKey.key_prefix == key_prefix, APIKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    # Verify hash
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    if key_hash != api_key.key_hash:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Update last used
    api_key.last_used_at = datetime.utcnow()
    api_key.total_calls = (api_key.total_calls or 0) + 1
    await db.commit()

    return api_key


@router.post("/verify")
async def verify_photo(
    file: UploadFile = File(..., description="Photo file (JPEG)"),
    latitude: float = Form(..., description="GPS latitude"),
    longitude: float = Form(..., description="GPS longitude"),
    accuracy: Optional[float] = Form(None, description="GPS accuracy in meters"),
    expected_latitude: Optional[float] = Form(None, description="Expected location latitude"),
    expected_longitude: Optional[float] = Form(None, description="Expected location longitude"),
    tolerance_meters: Optional[float] = Form(1000, description="Location tolerance in meters"),
    captured_at: Optional[str] = Form(None, description="Capture timestamp ISO 8601"),
    api_key: APIKey = Depends(validate_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Stateless photo verification.

    Send a photo + GPS coordinates, get a trust score back.
    No vendor/campaign context needed — pure verification.
    """
    # Read file
    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size > 10 * 1024 * 1024:  # 10MB limit for API
        raise HTTPException(status_code=400, detail="File too large. Maximum 10MB.")

    # File hash for dedup detection
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # GPS quality check
    gps_quality_score = 1.0
    gps_quality_passed = True
    if accuracy and accuracy > 100:
        gps_quality_score = max(0.3, 1.0 - (accuracy - 100) / 500)
        if accuracy > 500:
            gps_quality_passed = False

    # Freshness check
    freshness_score = 1.0
    freshness_passed = True
    age_seconds = None
    if captured_at:
        try:
            capture_time = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            age_seconds = (datetime.utcnow() - capture_time.replace(tzinfo=None)).total_seconds()
            if age_seconds > 3600:  # More than 1 hour old
                freshness_score = max(0.2, 1.0 - age_seconds / 86400)
            if age_seconds > 86400:  # More than 1 day old
                freshness_passed = False
        except ValueError:
            pass

    # Location match check
    location_score = 0.5  # Neutral if no expected location
    location_passed = True
    distance_meters = None
    flags = []

    if expected_latitude is not None and expected_longitude is not None:
        # Haversine distance
        R = 6371000
        phi1, phi2 = math.radians(latitude), math.radians(expected_latitude)
        dphi = math.radians(expected_latitude - latitude)
        dlam = math.radians(expected_longitude - longitude)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        distance_meters = 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        if distance_meters <= tolerance_meters:
            location_score = max(0.7, 1.0 - (distance_meters / tolerance_meters) * 0.3)
            location_passed = True
        elif distance_meters <= tolerance_meters * 2:
            location_score = 0.4
            location_passed = False
            flags.append("LOCATION_MODERATE_DEVIATION")
        else:
            location_score = 0.1
            location_passed = False
            flags.append("LOCATION_FAR_FROM_EXPECTED")

    # Compute overall confidence
    weights = {"location": 0.4, "gps_quality": 0.3, "freshness": 0.3}
    confidence = (
        location_score * weights["location"] +
        gps_quality_score * weights["gps_quality"] +
        freshness_score * weights["freshness"]
    )

    # Determine status
    if "LOCATION_FAR_FROM_EXPECTED" in flags:
        verification_status = "rejected"
    elif confidence >= 0.65:
        verification_status = "verified"
    elif confidence >= 0.40:
        verification_status = "flagged"
    else:
        verification_status = "rejected"

    return {
        "verification_id": file_hash[:16],  # Short ID for reference
        "confidence": round(confidence, 2),
        "status": verification_status,
        "flags": flags,
        "checks": {
            "location_match": {
                "score": round(location_score, 2),
                "passed": location_passed,
                "distance_meters": round(distance_meters, 1) if distance_meters else None,
            },
            "gps_quality": {
                "score": round(gps_quality_score, 2),
                "passed": gps_quality_passed,
                "accuracy_meters": accuracy,
            },
            "freshness": {
                "score": round(freshness_score, 2),
                "passed": freshness_passed,
                "age_seconds": round(age_seconds) if age_seconds else None,
            },
        },
    }


# API Key management endpoints (for the client dashboard)
@router.post("/keys", tags=["api-keys"])
async def create_api_key(
    name: str = Form("Production Key"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key. Returns the raw key ONCE."""
    from app.middleware.tenant_context import get_current_tenant
    from app.core.deps import get_current_client
    # This needs client auth, not API key auth
    # For now, require tenant context (client logged in)
    tenant_id = get_current_tenant(request)

    # Generate key
    raw_key = "tc_live_" + secrets.token_hex(16)
    key_prefix = raw_key[:12]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    # Find client_id from tenant
    from app.models.client import Client
    client_result = await db.execute(
        select(Client).where(Client.tenant_id == tenant_id)
    )
    client = client_result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=400, detail="Client not found")

    api_key = APIKey(
        client_id=client.client_id,
        tenant_id=tenant_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=name,
        permissions=["verify"],
        rate_limit_per_minute=60,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return {
        "key_id": str(api_key.key_id),
        "name": api_key.name,
        "key": raw_key,  # SHOWN ONCE ONLY
        "prefix": key_prefix,
        "created_at": api_key.created_at.isoformat(),
        "message": "Save this key now. It cannot be shown again.",
    }


@router.get("/keys", tags=["api-keys"])
async def list_api_keys(
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the current client (shows prefix only, not full key)."""
    from app.middleware.tenant_context import get_current_tenant
    tenant_id = get_current_tenant(request)

    result = await db.execute(
        select(APIKey).where(APIKey.tenant_id == tenant_id).order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()

    return [
        {
            "key_id": str(k.key_id),
            "name": k.name,
            "prefix": k.key_prefix + "****",
            "is_active": k.is_active,
            "total_calls": k.total_calls,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "created_at": k.created_at.isoformat(),
        }
        for k in keys
    ]


@router.delete("/keys/{key_id}", tags=["api-keys"])
async def revoke_api_key(
    key_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key (set inactive)."""
    from app.middleware.tenant_context import get_current_tenant
    tenant_id = get_current_tenant(request)

    result = await db.execute(
        select(APIKey).where(APIKey.key_id == key_id, APIKey.tenant_id == tenant_id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    await db.commit()

    return {"status": "revoked", "key_id": key_id}
