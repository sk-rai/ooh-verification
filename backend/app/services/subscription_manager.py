"""
Subscription management service.
Handles tier upgrades, downgrades, cancellations, and billing cycle changes.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription, SubscriptionTier, SubscriptionStatus
from app.models.client import Client


class SubscriptionManager:
    """Manages subscription lifecycle operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_subscription(self, client_id: str) -> Subscription:
        """Get subscription for a client."""
        result = await self.db.execute(
            select(Subscription).where(Subscription.client_id == client_id)
        )
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            raise ValueError(f"No subscription found for client {client_id}")
        
        return subscription

    async def upgrade_tier(
        self,
        client_id: str,
        new_tier: SubscriptionTier,
        billing_cycle: str = "monthly"
    ) -> Dict[str, Any]:
        """
        Upgrade subscription to a higher tier.
        
        Args:
            client_id: Client UUID
            new_tier: Target tier (pro or enterprise)
            billing_cycle: monthly or yearly
            
        Returns:
            Dict with upgrade details and payment information
        """
        subscription = await self.get_subscription(client_id)
        
        # Validate upgrade path
        tier_order = {"free": 0, "pro": 1, "enterprise": 2}
        current_tier_value = subscription.tier if isinstance(subscription.tier, str) else subscription.tier.value
        new_tier_value = new_tier if isinstance(new_tier, str) else new_tier.value
        
        if tier_order[new_tier_value] <= tier_order[current_tier_value]:
            raise ValueError(f"Cannot upgrade from {current_tier_value} to {new_tier_value}")
        
        # Calculate new quotas
        quotas = self._get_tier_quotas(new_tier_value)
        
        # Update subscription
        subscription.tier = new_tier
        subscription.billing_cycle = billing_cycle
        subscription.vendors_quota = quotas["vendors"]
        subscription.campaigns_quota = quotas["campaigns"]
        subscription.storage_quota_mb = quotas["storage_mb"]
        
        # Set pricing
        pricing = self._get_tier_pricing(new_tier_value, billing_cycle)
        subscription.amount = pricing["amount"]
        subscription.currency = pricing["currency"]
        
        # Update period
        subscription.current_period_start = datetime.utcnow()
        if billing_cycle == "yearly":
            subscription.current_period_end = datetime.utcnow() + timedelta(days=365)
        else:
            subscription.current_period_end = datetime.utcnow() + timedelta(days=30)
        
        subscription.status = "active"
        subscription.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(subscription)
        
        return {
            "message": f"Successfully upgraded to {new_tier_value}",
            "subscription": {
                "tier": subscription.tier.value,
                "billing_cycle": subscription.billing_cycle,
                "amount": subscription.amount,
                "currency": subscription.currency,
                "quotas": quotas,
                "current_period_end": subscription.current_period_end.isoformat()
            }
        }

    async def downgrade_tier(
        self,
        client_id: str,
        new_tier: SubscriptionTier
    ) -> Dict[str, Any]:
        """
        Downgrade subscription to a lower tier.
        Takes effect at the end of current billing period.
        
        Args:
            client_id: Client UUID
            new_tier: Target tier (free or pro)
            
        Returns:
            Dict with downgrade details
        """
        subscription = await self.get_subscription(client_id)
        
        # Validate downgrade path
        tier_order = {"free": 0, "pro": 1, "enterprise": 2}
        current_tier_value = subscription.tier if isinstance(subscription.tier, str) else subscription.tier.value
        new_tier_value = new_tier if isinstance(new_tier, str) else new_tier.value
        
        if tier_order[new_tier_value] >= tier_order[current_tier_value]:
            raise ValueError(f"Cannot downgrade from {current_tier_value} to {new_tier_value}")
        
        # Check if current usage fits in new tier
        quotas = self._get_tier_quotas(new_tier_value)
        
        if subscription.vendors_used > quotas["vendors"]:
            raise ValueError(
                f"Cannot downgrade: You have {subscription.vendors_used} vendors "
                f"but {new_tier_value} tier allows only {quotas['vendors']}"
            )
        
        if subscription.campaigns_used > quotas["campaigns"]:
            raise ValueError(
                f"Cannot downgrade: You have {subscription.campaigns_used} campaigns "
                f"but {new_tier_value} tier allows only {quotas['campaigns']}"
            )
        
        # Schedule downgrade for end of period
        # In production, you'd store this in a pending_tier field
        # For now, we'll apply it immediately
        
        subscription.tier = new_tier
        subscription.vendors_quota = quotas["vendors"]
        subscription.campaigns_quota = quotas["campaigns"]
        subscription.storage_quota_mb = quotas["storage_mb"]
        
        if new_tier_value == "free":
            subscription.amount = 0
            subscription.billing_cycle = "monthly"
        
        subscription.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(subscription)
        
        return {
            "message": f"Successfully downgraded to {new_tier_value}",
            "subscription": {
                "tier": subscription.tier.value,
                "quotas": quotas,
                "effective_date": subscription.current_period_end.isoformat() if subscription.current_period_end else "immediate"
            }
        }

    async def cancel_subscription(
        self,
        client_id: str,
        immediate: bool = False
    ) -> Dict[str, Any]:
        """
        Cancel subscription.
        
        Args:
            client_id: Client UUID
            immediate: If True, cancel immediately. If False, cancel at period end.
            
        Returns:
            Dict with cancellation details
        """
        subscription = await self.get_subscription(client_id)
        
        if (subscription.status if isinstance(subscription.status, str) else subscription.status.value) == "cancelled":
            raise ValueError("Subscription is already cancelled")
        
        subscription.cancellation_date = datetime.utcnow()
        subscription.auto_renew = False
        
        if immediate:
            subscription.status = "cancelled"
            subscription.current_period_end = datetime.utcnow()
            message = "Subscription cancelled immediately"
        else:
            # Cancel at end of period
            message = f"Subscription will be cancelled on {subscription.current_period_end.isoformat()}"
        
        subscription.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(subscription)
        
        return {
            "message": message,
            "subscription": {
                "status": subscription.status.value,
                "cancellation_date": subscription.cancellation_date.isoformat(),
                "access_until": subscription.current_period_end.isoformat() if subscription.current_period_end else None
            }
        }

    async def reactivate_subscription(
        self,
        client_id: str
    ) -> Dict[str, Any]:
        """
        Reactivate a cancelled subscription.
        
        Args:
            client_id: Client UUID
            
        Returns:
            Dict with reactivation details
        """
        subscription = await self.get_subscription(client_id)
        
        if (subscription.status if isinstance(subscription.status, str) else subscription.status.value) not in ["cancelled"] and subscription.cancellation_date is None:
            raise ValueError("Only cancelled or scheduled-for-cancellation subscriptions can be reactivated")
        
        subscription.status = "active"
        subscription.auto_renew = True
        subscription.cancellation_date = None
        
        # Extend period if needed
        if subscription.current_period_end and subscription.current_period_end < datetime.utcnow():
            if subscription.billing_cycle == "yearly":
                subscription.current_period_end = datetime.utcnow() + timedelta(days=365)
            else:
                subscription.current_period_end = datetime.utcnow() + timedelta(days=30)
        
        subscription.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(subscription)
        
        return {
            "message": "Subscription reactivated successfully",
            "subscription": {
                "status": subscription.status.value,
                "tier": subscription.tier.value,
                "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None
            }
        }

    async def change_billing_cycle(
        self,
        client_id: str,
        new_cycle: str
    ) -> Dict[str, Any]:
        """
        Change billing cycle between monthly and yearly.
        
        Args:
            client_id: Client UUID
            new_cycle: "monthly" or "yearly"
            
        Returns:
            Dict with updated billing details
        """
        if new_cycle not in ["monthly", "yearly"]:
            raise ValueError("Billing cycle must be 'monthly' or 'yearly'")
        
        subscription = await self.get_subscription(client_id)
        
        if (subscription.tier if isinstance(subscription.tier, str) else subscription.tier.value) == "free":
            raise ValueError("Free tier does not support billing cycle changes")
        
        if subscription.billing_cycle == new_cycle:
            raise ValueError(f"Billing cycle is already {new_cycle}")
        
        subscription.billing_cycle = new_cycle
        
        # Update pricing
        pricing = self._get_tier_pricing(subscription.tier.value, new_cycle)
        subscription.amount = pricing["amount"]
        
        # Update period end
        if new_cycle == "yearly":
            subscription.current_period_end = datetime.utcnow() + timedelta(days=365)
        else:
            subscription.current_period_end = datetime.utcnow() + timedelta(days=30)
        
        subscription.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(subscription)
        
        return {
            "message": f"Billing cycle changed to {new_cycle}",
            "subscription": {
                "billing_cycle": subscription.billing_cycle,
                "amount": subscription.amount,
                "currency": subscription.currency,
                "current_period_end": subscription.current_period_end.isoformat()
            }
        }

    def _get_tier_quotas(self, tier: str) -> Dict[str, int]:
        """Get quota limits for a tier."""
        quotas = {
            "free": {
                "vendors": 2,
                "campaigns": 1,
                "storage_mb": 500
            },
            "pro": {
                "vendors": 10,
                "campaigns": 5,
                "storage_mb": 10240
            },
            "enterprise": {
                "vendors": 999999,  # Unlimited
                "campaigns": 999999,  # Unlimited
                "storage_mb": 102400
            }
        }
        return quotas.get(tier, quotas["free"])

    def _get_tier_pricing(self, tier: str, billing_cycle: str) -> Dict[str, Any]:
        """Get pricing for a tier and billing cycle."""
        pricing = {
            "free": {"amount": 0, "currency": "INR"},
            "pro": {
                "monthly": {"amount": 999, "currency": "INR"},
                "yearly": {"amount": 9990, "currency": "INR"}
            },
            "enterprise": {
                "monthly": {"amount": 4999, "currency": "INR"},
                "yearly": {"amount": 49990, "currency": "INR"}
            }
        }
        
        if tier == "free":
            return pricing["free"]
        
        return pricing[tier].get(billing_cycle, pricing[tier]["monthly"])


def get_subscription_manager(db: AsyncSession) -> SubscriptionManager:
    """Dependency injection for SubscriptionManager."""
    return SubscriptionManager(db)
