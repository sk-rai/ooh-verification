"""
TrustCapture Backend - Main FastAPI Application
"""
from dotenv import load_dotenv
load_dotenv()  # Load .env file before any other imports

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import Request
import os

from app.api import auth, clients, vendors, campaigns, photos, subscriptions, webhooks, reports, campaign_locations, tenants, assignments, bulk, admin, vendor_campaigns, integrity, analytics, admin_queue, app_config, evidence, site_visits, tracks, verify_api, report_email
from app.core.database import close_db
from app.core.config import settings
from app.middleware.tenant_context import TenantContextMiddleware

# Create FastAPI app
app = FastAPI(
    title="TrustCapture API",
    description="Tamper-proof photo verification system with multi-sensor geolocation triangulation",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS - MUST be before routers
# Build CORS origins from env var + localhost defaults
cors_origins = settings.cors_origins_list + [
    "https://app.trustcaptures.com",
    "https://trustcapture-web.onrender.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
]
# Deduplicate
cors_origins = list(dict.fromkeys(cors_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add tenant context middleware
app.add_middleware(TenantContextMiddleware)

# Global exception handler to ensure CORS headers on errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all exceptions and return JSON with CORS headers."""
    import traceback

    print(f"❌ Unhandled exception: {exc}")
    print(traceback.format_exc())
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Internal server error: {str(exc)}",
            "type": type(exc).__name__
        }
    )

# Include routers AFTER middleware
app.include_router(auth.router)
app.include_router(tenants.router)
app.include_router(clients.router)
app.include_router(vendors.router)
app.include_router(vendor_campaigns.router)  # Vendor-facing campaign endpoints
app.include_router(campaigns.router)
app.include_router(campaign_locations.router)
app.include_router(assignments.router)
app.include_router(bulk.router)
app.include_router(admin.router)
app.include_router(photos.router)
app.include_router(subscriptions.router)
app.include_router(webhooks.router)
app.include_router(reports.router)
app.include_router(integrity.router)
app.include_router(analytics.router)
app.include_router(admin_queue.router)
app.include_router(app_config.router)
app.include_router(evidence.router)
app.include_router(site_visits.router)
app.include_router(tracks.router)
app.include_router(verify_api.router)
app.include_router(report_email.router)

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    # Schema is managed exclusively by Alembic migrations (M2).
    # The startup DDL that previously created tables, columns and indexes here has been removed.
    # start.sh runs `alembic upgrade head` before uvicorn starts, so all schema is ready before
    # any request is handled. If migrations fail, start.sh exits non-zero and the container does not serve.

    # Start task queue worker (runtime concern, not schema)
    from app.services.queue.worker import task_worker
    import app.services.queue.handlers.email_handler
    import app.services.queue.handlers.audit_handler
    import app.services.queue.handlers.webhook_handler
    import app.services.queue.handlers.pdf_handler
    import app.services.queue.handlers.analytics_handler
    try:
        await task_worker.start()
    except Exception as e:
        print(f"Warning: Task worker failed to start: {e}")

    print("🚀 TrustCapture API starting up...")
    print(f"📚 API Documentation: http://localhost:8000/api/docs")
    print(f"🔐 Authentication endpoints available at /api/auth")
    print(f"👤 Client management endpoints available at /api/clients")
    print(f"👥 Vendor management endpoints available at /api/vendors")
    print(f"📋 Campaign management endpoints available at /api/campaigns")
    print(f"📍 Campaign locations endpoints available at /api/campaigns/:id/locations")
    print(f"📸 Photo upload endpoints available at /api/photos")
    print(f"📊 Reports endpoints available at /api/reports")
    print(f"🌐 CORS origins: {cors_origins}")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("👋 TrustCapture API shutting down...")
    from app.services.queue.worker import task_worker
    try:
        await task_worker.stop()
    except Exception as e:
        print(f"Warning: Task worker stop error: {e}")
    await close_db()



# App version check endpoint (no auth required)
@app.get("/api/app/version-check")
async def app_version_check(platform: str = "android", current_version: int = 1):
    """
    Check if an app update is available.
    
    Returns update info for the mobile app to decide whether to prompt user.
    No authentication required — called before login.
    """
    # Version config — update these when releasing new versions
    LATEST_VERSIONS = {
        "android": {
            "version_code": 11,
            "version_name": "1.3.0",
            "min_supported_version": 8,  # Force update below this
            "update_url": "https://play.google.com/store/apps/details?id=com.lynksavvy.trustcapture",
            "message": "New: video capture, voice notes, quick capture mode, configurable settings"
        },
        "ios": {
            "version_code": 1,
            "version_name": "1.0.0",
            "min_supported_version": 1,
            "update_url": "",
            "message": ""
        }
    }

    platform_config = LATEST_VERSIONS.get(platform.lower(), LATEST_VERSIONS["android"])
    latest = platform_config["version_code"]
    min_supported = platform_config["min_supported_version"]

    update_available = current_version < latest
    force_update = current_version < min_supported

    return {
        "update_available": update_available,
        "force_update": force_update,
        "latest_version": latest,
        "latest_version_name": platform_config["version_name"],
        "update_url": platform_config["update_url"],
        "message": platform_config["message"] if update_available else ""
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "TrustCapture API",
        "version": "1.0.0"
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "TrustCapture API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/health"
    }
