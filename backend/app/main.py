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

from app.api import auth, clients, vendors, campaigns, photos, subscriptions, webhooks, reports, campaign_locations, tenants, assignments, bulk
from app.core.database import close_db
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
    ],
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
app.include_router(campaigns.router)
app.include_router(campaign_locations.router)
app.include_router(assignments.router)  # Campaign-vendor assignments
app.include_router(bulk.router)  # Bulk operations
app.include_router(photos.router)
app.include_router(subscriptions.router)
app.include_router(webhooks.router)
app.include_router(reports.router)

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    print("🚀 TrustCapture API starting up...")
    print(f"📚 API Documentation: http://localhost:8000/api/docs")
    print(f"🔐 Authentication endpoints available at /api/auth")
    print(f"👤 Client management endpoints available at /api/clients")
    print(f"👥 Vendor management endpoints available at /api/vendors")
    print(f"📋 Campaign management endpoints available at /api/campaigns")
    print(f"📍 Campaign locations endpoints available at /api/campaigns/:id/locations")
    print(f"📸 Photo upload endpoints available at /api/photos")
    print(f"📊 Reports endpoints available at /api/reports")
    print(f"🌐 CORS: localhost:3000, 127.0.0.1:3000, localhost:5173")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("👋 TrustCapture API shutting down...")
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
