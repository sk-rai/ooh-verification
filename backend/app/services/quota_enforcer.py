"""
Quota enforcement service for subscription-based usage limits.
Tracks and enforces limits on photos, vendors, campaigns, and storage.
"""
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime

from app.models.subscription import Subscription
from app.models.client import Client, SubscriptionTier, SubscriptionStatus
from app.models.vendor import Vendor
from app.models.campaign import Campaign
from app.models.photo import Photo


class QuotaExceededError(Exception):
    """Raised when a quota limit is exceeded."""
    
    def __init__(self, message: str, quota_type: str, current: int, limit: int, tier: str):
        self.message = message
        self.quota_type = quota_type
        self.current = current
        self.limit = limit
        self.tier = tier
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "error": "quota_exceeded",
            "message": self.message,
            "quota_type": self.quota_type,
            "current_usage": self.current,
            "quota_limit": self.limit,
            "current_tier": self.tier,
            "upgrade_required": True,
            "suggested_action": self._get_suggested_action()
        }
    
    def _get_suggested_action(self) -> str:
        """Get suggested action based on current tier."""
        if self.tier == "free":
            return "Upgrade to Pro tier for higher limits"
        elif self.tier == "pro":
            return "Upgrade to Enterprise tier for unlimited access"
        else:
            return "Contact support for assistance"


class QuotaEnforcer:
    """
    Service for enforcing subscription quotas.
    
    Handles:
    - Photo upload limits
    - Vendor creation limits
    - Campaign creation limits
    - Storage limits
    - Usage tracking and statistics
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def _get_subscription(self, client_id: str) -> Subscription:
        """Get client's subscription."""
        result = await self.db.execute(
            select(Subscription).where(Subscription.client_id == client_id)
        )
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            raise ValueError(f"No subscription found for client {client_id}")
        
        return subscription
    
    async def check_photo_quota(self, client_id: str) -> bool:
        """
        Check if client can upload more photos.
        
        Args:
            client_id: Client ID
            
        Returns:
            True if quota available
            
        Raises:
            QuotaExceededError: If photo quota exceeded
        """
        subscription = await self._get_subscription(client_id)
        
        # Check if subscription is active
        if subscription.status != SubscriptionStatus.ACTIVE:
            raise QuotaExceededError(
                message="Subscription is not active. Please renew your subscription.",
                quota_type="subscription_status",
                current=0,
                limit=0,
                tier=subscription.tier.value
            )
        
        # Enterprise tier has unlimited photos
        if subscription.tier == SubscriptionTier.ENTERPRISE:
            return True
        
        # Check photo quota
        if subscription.photos_used >= subscription.photos_quota:
            raise QuotaExceededError(
                message=f"Photo quota exceeded. You have used {subscription.photos_used} of {subscription.photos_quota} photos this month.",
                quota_type="photos",
                current=subscription.photos_used,
                limit=subscription.photos_quota,
                tier=subscription.tier.value
            )
        
        return True
    
    async def check_vendor_quota(self, client_id: str) -> bool:
        """
        Check if client can create more vendors.
        
        Args:
            client_id: Client ID
            
        Returns:
            True if quota available
            
        Raises:
            QuotaExceededError: If vendor quota exceeded
        """
        subscription = await self._get_subscription(client_id)
        
        # Check if subscription is active
        if subscription.status != SubscriptionStatus.ACTIVE:
            raise QuotaExceededError(
                message="Subscription is not active. Please renew your subscription.",
                quota_type="subscription_status",
                current=0,
                limit=0,
                tier=subscription.tier.value
            )
        
        # Enterprise tier has unlimited vendors
        if subscription.tier == SubscriptionTier.ENTERPRISE:
            return True
        
        # Check vendor quota
        if subscription.vendors_used >= subscription.vendors_quota:
            raise QuotaExceededError(
                message=f"Vendor quota exceeded. You have {subscription.vendors_used} of {subscription.vendors_quota} vendors.",
                quota_type="vendors",
                current=subscription.vendors_used,
                limit=subscription.vendors_quota,
                tier=subscription.tier.value
            )
        
        return True
    
    async def check_campaign_quota(self, client_id: str) -> bool:
        """
        Check if client can create more campaigns.
        
        Args:
            client_id: Client ID
            
        Returns:
            True if quota available
            
        Raises:
            QuotaExceededError: If campaign quota exceeded
        """
        subscription = await self._get_subscription(client_id)
        
        # Check if subscription is active
        if subscription.status != SubscriptionStatus.ACTIVE:
            raise QuotaExceededError(
                message="Subscription is not active. Please renew your subscription.",
                quota_type="subscription_status",
                current=0,
                limit=0,
                tier=subscription.tier.value
            )
        
        # Enterprise tier has unlimited campaigns
        if subscription.tier == SubscriptionTier.ENTERPRISE:
            return True
        
        # Check campaign quota
        if subscription.campaigns_used >= subscription.campaigns_quota:
            raise QuotaExceededError(
                message=f"Campaign quota exceeded. You have {subscription.campaigns_used} of {subscription.campaigns_quota} campaigns.",
                quota_type="campaigns",
                current=subscription.campaigns_used,
                limit=subscription.campaigns_quota,
                tier=subscription.tier.value
            )
        
        return True
    
    async def check_storage_quota(self, client_id: str, file_size_mb: float) -> bool:
        """
        Check if client has enough storage quota for file.
        
        Args:
            client_id: Client ID
            file_size_mb: File size in MB
            
        Returns:
            True if storage available
            
        Raises:
            QuotaExceededError: If storage quota exceeded
        """
        subscription = await self._get_subscription(client_id)
        
        # Check if subscription is active
        if subscription.status != SubscriptionStatus.ACTIVE:
            raise QuotaExceededError(
                message="Subscription is not active. Please renew your subscription.",
                quota_type="subscription_status",
                current=0,
                limit=0,
                tier=subscription.tier.value
            )
        
        # Check storage quota
        new_usage = subscription.storage_used_mb + file_size_mb
        if new_usage > subscription.storage_quota_mb:
            raise QuotaExceededError(
                message=f"Storage quota exceeded. You have used {subscription.storage_used_mb:.2f} MB of {subscription.storage_quota_mb} MB. This file requires {file_size_mb:.2f} MB.",
                quota_type="storage",
                current=int(subscription.storage_used_mb),
                limit=subscription.storage_quota_mb,
                tier=subscription.tier.value
            )
        
        return True
    
    async def increment_photo_usage(self, client_id: str) -> None:
        """
        Increment photo usage counter.
        
        Args:
            client_id: Client ID
        """
        subscription = await self._get_subscription(client_id)
        subscription.photos_used += 1
        await self.db.commit()
    
    async def increment_vendor_usage(self, client_id: str) -> None:
        """
        Increment vendor usage counter.
        
        Args:
            client_id: Client ID
        """
        subscription = await self._get_subscription(client_id)
        subscription.vendors_used += 1
        await self.db.commit()
    
    async def increment_campaign_usage(self, client_id: str) -> None:
        """
        Increment campaign usage counter.
        
        Args:
            client_id: Client ID
        """
        subscription = await self._get_subscription(client_id)
        subscription.campaigns_used += 1
        await self.db.commit()
    
    async def increment_storage_usage(self, client_id: str, file_size_mb: float) -> None:
        """
        Increment storage usage counter.
        
        Args:
            client_id: Client ID
            file_size_mb: File size in MB
        """
        subscription = await self._get_subscription(client_id)
        subscription.storage_used_mb += int(file_size_mb)
        await self.db.commit()
    
    async def decrement_vendor_usage(self, client_id: str) -> None:
        """
        Decrement vendor usage counter (when vendor is deleted).
        
        Args:
            client_id: Client ID
        """
        subscription = await self._get_subscription(client_id)
        if subscription.vendors_used > 0:
            subscription.vendors_used -= 1
            await self.db.commit()
    
    async def decrement_campaign_usage(self, client_id: str) -> None:
        """
        Decrement campaign usage counter (when campaign is deleted).
        
        Args:
            client_id: Client ID
        """
        subscription = await self._get_subscription(client_id)
        if subscription.campaigns_used > 0:
            subscription.campaigns_used -= 1
            await self.db.commit()
    
    async def decrement_storage_usage(self, client_id: str, file_size_mb: float) -> None:
        """
        Decrement storage usage counter (when photo is deleted).
        
        Args:
            client_id: Client ID
            file_size_mb: File size in MB
        """
        subscription = await self._get_subscription(client_id)
        subscription.storage_used_mb = max(0, subscription.storage_used_mb - int(file_size_mb))
        await self.db.commit()
    
    async def reset_monthly_quotas(self, client_id: str) -> None:
        """
        Reset monthly quotas (photos) at billing cycle start.
        
        Args:
            client_id: Client ID
        """
        subscription = await self._get_subscription(client_id)
        subscription.photos_used = 0
        # Note: Storage, vendors, and campaigns are not reset monthly
        await self.db.commit()
    
    async def get_usage_stats(self, client_id: str) -> Dict[str, Any]:
        """
        Get comprehensive usage statistics.
        
        Args:
            client_id: Client ID
            
        Returns:
            Dictionary with usage statistics
        """
        subscription = await self._get_subscription(client_id)
        
        return {
            "subscription": {
                "tier": subscription.tier.value,
                "status": subscription.status.value,
                "billing_cycle": subscription.billing_cycle,
                "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
                "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None
            },
            "photos": {
                "used": subscription.photos_used,
                "quota": subscription.photos_quota if subscription.tier != SubscriptionTier.ENTERPRISE else "unlimited",
                "percentage": subscription.quota_percentage_used,
                "remaining": max(0, subscription.photos_quota - subscription.photos_used) if subscription.tier != SubscriptionTier.ENTERPRISE else "unlimited"
            },
            "vendors": {
                "used": subscription.vendors_used,
                "quota": subscription.vendors_quota if subscription.tier != SubscriptionTier.ENTERPRISE else "unlimited",
                "remaining": max(0, subscription.vendors_quota - subscription.vendors_used) if subscription.tier != SubscriptionTier.ENTERPRISE else "unlimited"
            },
            "campaigns": {
                "used": subscription.campaigns_used,
                "quota": subscription.campaigns_quota if subscription.tier != SubscriptionTier.ENTERPRISE else "unlimited",
                "remaining": max(0, subscription.campaigns_quota - subscription.campaigns_used) if subscription.tier != SubscriptionTier.ENTERPRISE else "unlimited"
            },
            "storage": {
                "used_mb": subscription.storage_used_mb,
                "quota_mb": subscription.storage_quota_mb,
                "percentage": subscription.storage_percentage_used,
                "remaining_mb": max(0, subscription.storage_quota_mb - subscription.storage_used_mb)
            }
        }
    
    async def sync_usage_counters(self, client_id: str) -> None:
        """
        Synchronize usage counters with actual database counts.
        Useful for fixing discrepancies.
        
        Args:
            client_id: Client ID
        """
        subscription = await self._get_subscription(client_id)
        
        # Count actual vendors
        vendor_count = await self.db.execute(
            select(func.count(Vendor.vendor_id)).where(Vendor.client_id == client_id)
        )
        actual_vendors = vendor_count.scalar() or 0
        
        # Count actual campaigns
        campaign_count = await self.db.execute(
            select(func.count(Campaign.campaign_id)).where(Campaign.client_id == client_id)
        )
        actual_campaigns = campaign_count.scalar() or 0
        
        # Update counters
        subscription.vendors_used = actual_vendors
        subscription.campaigns_used = actual_campaigns
        
        await self.db.commit()


def get_quota_enforcer(db: AsyncSession) -> QuotaEnforcer:
    """Get QuotaEnforcer instance."""
    return QuotaEnforcer(db)
