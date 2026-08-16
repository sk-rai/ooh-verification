"""
App Configuration endpoint.

Returns capture config, upload config, UI config, branding, and version info.
Called by Android on every app start. No auth required.
"""
from fastapi import APIRouter, Request
from app.middleware.tenant_context import get_current_tenant

router = APIRouter(prefix="/api/app", tags=["app-config"])


# Default capture config (can be overridden per-tenant later)
DEFAULT_CAPTURE_CONFIG = {
    # Photo settings
    "photo_enabled": True,
    "photo_max_dimension": 3000,
    "photo_compression_quality": 90,
    "max_photos_per_location": 10,

    # Video settings
    "video_enabled": True,
    "max_video_duration_seconds": 60,
    "max_videos_per_location": 5,
    "video_resolution": "720p",

    # Voice note settings
    "voice_note_enabled": True,
    "max_voice_duration_seconds": 120,
    "max_voice_notes_per_location": 5,

    # Text note settings
    "text_note_enabled": True,
    "max_text_note_length": 500,

    # Watermark settings
    "watermark_enabled": True,
    "watermark_opacity": 160,
    "watermark_height_percent": 15,

    # Camera settings
    "camera_facing": "back",
    "compass_enabled": True,
    "gallery_upload_allowed": False,

    # GPS settings
    "gps_required": True,
    "gps_min_accuracy_meters": 50,
    "gps_timeout_seconds": 30,
    "gps_interval_high_ms": 5000,
    "gps_interval_balanced_ms": 15000,

    # Security settings
    "allow_emulator_capture": True,
    "allow_rooted_capture": True,
}

DEFAULT_UPLOAD_CONFIG = {
    "endpoint": "/api/evidence/upload",
    "max_file_size_mb": 50,
    "retry_max_attempts": 5,
    "upload_timeout_photo_ms": 60000,
    "upload_timeout_video_ms": 120000,
    "wifi_only_upload": False,
    "upload_periodic_interval_minutes": 15,
}

DEFAULT_UI_CONFIG = {
    "quick_capture_enabled": True,
    "categories": ["accident", "damage", "inspection", "delivery_proof", "hazard", "other"],
    "features": {
        "campaigns": True,
        "quick_capture": True,
        "settings": True,
        "tracking": False,
    },
    "maintenance": {
        "enabled": True,
        "message": "",
    },
}

DEFAULT_TRACKING_CONFIG = {
    "enabled": True,
    "interval_minutes": 30,
    "max_duration_hours": 8,
    "sync_interval_minutes": 30,
    "min_accuracy_meters": 100,
    "stop_on_app_close": True,
    "collect_battery_level": True,
}

DEFAULT_BRANDING = {
    "primary_color": "#3B82F6",
    "secondary_color": "#10B981",
    "tenant_name": "TrustCapture",
    "logo_url": None,
    "watermark_text": "TrustCapture",
}

# Version config — update when releasing new app versions
VERSION_CONFIG = {
    "latest_version_code": 11,
    "latest_version_name": "1.3.0",
    "min_supported_version": 8,
    "update_url": "https://play.google.com/store/apps/details?id=com.lynksavvy.trustcapture",
    "message": "New: video capture, voice notes, quick capture mode, configurable settings",
}


@router.get("/config")
async def get_app_config(request: Request):
    """
    Get full app configuration.

    Called by Android on every app start. Returns capture settings,
    upload config, UI config, branding, and version info.

    No authentication required — needed before login.
    Per-tenant branding resolved from request origin.
    """
    # Try to resolve tenant for branding (non-fatal if not found)
    branding = dict(DEFAULT_BRANDING)
    try:
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import select
            from app.models.tenant_config import TenantConfig
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
                )
                tenant = result.scalar_one_or_none()
                if tenant:
                    branding = {
                        "primary_color": tenant.primary_color or DEFAULT_BRANDING["primary_color"],
                        "secondary_color": tenant.secondary_color or DEFAULT_BRANDING["secondary_color"],
                        "tenant_name": tenant.tenant_name or DEFAULT_BRANDING["tenant_name"],
                        "logo_url": tenant.logo_url,
                        "watermark_text": tenant.tenant_name or DEFAULT_BRANDING["watermark_text"],
                    }
    except Exception:
        pass  # Fall back to defaults

    return {
        "capture_config": DEFAULT_CAPTURE_CONFIG,
        "upload_config": DEFAULT_UPLOAD_CONFIG,
        "ui_config": DEFAULT_UI_CONFIG,
        "tracking_config": DEFAULT_TRACKING_CONFIG,
        "branding": branding,
        "version": VERSION_CONFIG,
    }
