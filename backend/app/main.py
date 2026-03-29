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

from app.api import auth, clients, vendors, campaigns, photos, subscriptions, webhooks, reports, campaign_locations, tenants, assignments, bulk, admin, vendor_campaigns, integrity, analytics, admin_queue
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

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    # Create task_queue table if it doesn't exist (raw SQL for reliability)
    from app.core.database import engine
    try:
        async with engine.begin() as conn:
            from sqlalchemy import text
            # Create enum type if not exists
            await conn.execute(text(
                "DO $$ BEGIN "
                "CREATE TYPE taskstatus AS ENUM ('pending','running','completed','failed','dead'); "
                "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
            ))
            # Create table if not exists
            await conn.execute(text('''
                CREATE TABLE IF NOT EXISTS task_queue (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    task_type VARCHAR(100) NOT NULL,
                    payload JSONB NOT NULL DEFAULT '{}',
                    status taskstatus NOT NULL DEFAULT 'pending',
                    priority INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    scheduled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    last_error TEXT,
                    tenant_id UUID
                );
            '''))
            # Create indexes if not exist
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_task_queue_task_type ON task_queue (task_type);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_task_queue_status ON task_queue (status);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_task_queue_tenant_id ON task_queue (tenant_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_task_queue_poll ON task_queue (status, scheduled_at, priority);"))
        print("✅ Task queue table ready")
    except Exception as e:
        print(f"⚠️ Task queue table creation warning: {e}")

    # Start task queue worker
    from app.services.queue.worker import task_worker
    # Import handlers to register them
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
