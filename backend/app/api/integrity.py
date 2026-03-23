"""
Play Integrity API - Verify Android device integrity tokens.

Endpoint: POST /api/integrity/verify
  - Receives integrity token from Android app
  - Decodes via Google Play Integrity API
  - Returns device/app/account integrity verdict

Requires GOOGLE_PLAY_INTEGRITY_ENABLED=true to be active.
When not configured, returns a 503 indicating the service is not yet active.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.services.play_integrity_service import get_play_integrity_service

router = APIRouter(prefix="/api/integrity", tags=["Play Integrity"])


class IntegrityVerifyRequest(BaseModel):
    integrity_token: str = Field(..., description="Token from Android IntegrityManager.requestIntegrityToken()")
    device_id: Optional[str] = Field(None, description="Device identifier for correlation")


class IntegrityVerifyResponse(BaseModel):
    device_integrity: bool = Field(False, description="Device passes Google's integrity checks (not rooted/emulated)")
    app_integrity: bool = Field(False, description="App is genuine Play Store install")
    account_integrity: bool = Field(False, description="User has a licensed/valid Google account")
    device_labels: List[str] = Field(default_factory=list, description="Raw device recognition labels from Google")
    app_recognition: str = Field("UNKNOWN", description="App recognition verdict")
    account_activity: str = Field("UNKNOWN", description="Account licensing verdict")
    verified_at: Optional[datetime] = None
    error: Optional[str] = None


@router.post("/verify", response_model=IntegrityVerifyResponse)
async def verify_integrity_token(request: IntegrityVerifyRequest):
    """
    Verify an Android Play Integrity token.

    The Android app calls IntegrityManager.requestIntegrityToken() and sends
    the resulting token here. This endpoint decodes it via Google's API and
    returns the parsed verdict.

    When GOOGLE_PLAY_INTEGRITY_ENABLED is not set, returns 503.
    """
    service = get_play_integrity_service()

    if not service.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Play Integrity verification is not yet configured. Set GOOGLE_PLAY_INTEGRITY_ENABLED=true and provide service account credentials.",
        )

    verdict = await service.verify_token(request.integrity_token)

    if verdict.error and verdict.error.startswith("google_api_error"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Google Play Integrity API returned an error: {verdict.error}",
        )

    return IntegrityVerifyResponse(
        device_integrity=verdict.device_integrity,
        app_integrity=verdict.app_integrity,
        account_integrity=verdict.account_integrity,
        device_labels=verdict.device_labels,
        app_recognition=verdict.app_recognition,
        account_activity=verdict.account_activity,
        verified_at=verdict.verified_at,
        error=verdict.error,
    )


@router.get("/status")
async def integrity_status():
    """Check if Play Integrity verification is configured and active."""
    service = get_play_integrity_service()
    return {
        "enabled": service.enabled,
        "package_name": service.package_name if service.enabled else None,
        "message": "Play Integrity API is active" if service.enabled else "Not configured — set GOOGLE_PLAY_INTEGRITY_ENABLED=true",
    }
