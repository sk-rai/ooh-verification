"""
TrustCapture Backend - Main FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.api import auth, clients, vendors, campaigns, photos, subscriptions, webhooks, reports
from app.core.database import close_db

# Create FastAPI app
app = FastAPI(
    title="TrustCapture API",
    description="Tamper-proof photo verification system with multi-sensor geolocation triangulation",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(vendors.router)
app.include_router(campaigns.router)
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
    print(f"📸 Photo upload endpoints available at /api/photos")
    print(f"📊 Reports endpoints available at /api/reports")


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
