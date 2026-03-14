"""
Database models for TrustCapture.

This module exports all SQLAlchemy models for the application.
Import Base from here to ensure all models are registered.
"""
from app.core.database import Base

# Import all models to register them with SQLAlchemy
from app.models.client import Client, SubscriptionTier, SubscriptionStatus
from app.models.vendor import Vendor, VendorStatus
from app.models.campaign import Campaign, CampaignType, CampaignStatus
from app.models.campaign_location import CampaignLocation
from app.models.location_profile import LocationProfile
from app.models.campaign_vendor_assignment import CampaignVendorAssignment
from app.models.photo import Photo, VerificationStatus
from app.models.sensor_data import SensorData
from app.models.photo_signature import PhotoSignature
from app.models.subscription import Subscription
from app.models.audit_log import AuditLog
from app.models.admin_user import AdminUser

# Export all models and enums
__all__ = [
    "Base",
    # Models
    "Client",
    "Vendor",
    "Campaign",
    "CampaignLocation",
    "LocationProfile",
    "CampaignVendorAssignment",
    "Photo",
    "SensorData",
    "PhotoSignature",
    "Subscription",
    "AuditLog",
    "AdminUser",
    # Enums
    "SubscriptionTier",
    "SubscriptionStatus",
    "VendorStatus",
    "CampaignType",
    "CampaignStatus",
    "VerificationStatus",
]
