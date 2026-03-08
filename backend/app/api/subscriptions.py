"""
Subscription management API endpoints.
Allows clients to view and manage their subscriptions and usage.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.core.deps import get_db, get_current_active_client
from app.models.client import Client
from app.services.quota_enforcer import get_quota_enforcer
from app.services.razorpay_service import get_razorpay_service
from app.services.stripe_service import get_stripe_service

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.get("/usage", response_model=Dict[str, Any])
async def get_usage_statistics(
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive usage statistics for the current client.
    
    Returns:
        - Subscription details (tier, status, billing cycle)
        - Photo usage (used, quota, percentage, remaining)
        - Vendor usage (used, quota, remaining)
        - Campaign usage (used, quota, remaining)
        - Storage usage (used MB, quota MB, percentage, remaining MB)
    
    Requirements:
        - Req 11.3: Usage tracking
        - Req 11.6: Analytics dashboard
    """
    enforcer = get_quota_enforcer(db)
    
    try:
        usage_stats = await enforcer.get_usage_stats(str(client.client_id))
        return usage_stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve usage statistics: {str(e)}"
        )


@router.get("/current")
async def get_current_subscription(
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current subscription details.
    
    Returns:
        - Subscription tier
        - Status
        - Billing cycle
        - Payment gateway
        - Current period dates
        - Auto-renewal status
    """
    enforcer = get_quota_enforcer(db)
    
    try:
        subscription = await enforcer._get_subscription(str(client.client_id))
        
        return {
            "subscription_id": str(subscription.subscription_id),
            "tier": subscription.tier.value,
            "status": subscription.status.value,
            "billing_cycle": subscription.billing_cycle,
            "payment_gateway": subscription.payment_gateway,
            "amount": subscription.amount,
            "currency": subscription.currency,
            "auto_renew": bool(subscription.auto_renew),
            "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
            "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            "trial_end_date": subscription.trial_end_date.isoformat() if subscription.trial_end_date else None,
            "cancellation_date": subscription.cancellation_date.isoformat() if subscription.cancellation_date else None,
            "created_at": subscription.created_at.isoformat(),
            "updated_at": subscription.updated_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve subscription: {str(e)}"
        )


@router.post("/sync-usage")
async def sync_usage_counters(
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Synchronize usage counters with actual database counts.
    
    Useful for fixing discrepancies between usage counters and actual data.
    Counts actual vendors and campaigns in the database and updates counters.
    
    Requirements:
        - Req 11.3: Usage tracking accuracy
    """
    enforcer = get_quota_enforcer(db)
    
    try:
        await enforcer.sync_usage_counters(str(client.client_id))
        
        # Get updated stats
        usage_stats = await enforcer.get_usage_stats(str(client.client_id))
        
        return {
            "message": "Usage counters synchronized successfully",
            "usage": usage_stats
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync usage counters: {str(e)}"
        )


@router.get("/tiers")
async def get_subscription_tiers():
    """
    Get available subscription tiers and their features.
    
    Returns information about Free, Pro, and Enterprise tiers.
    """
    return {
        "tiers": [
            {
                "name": "free",
                "display_name": "Free",
                "price_inr": 0,
                "price_usd": 0,
                "billing_cycles": ["monthly"],
                "features": {
                    "photos_per_month": 50,
                    "vendors": 2,
                    "campaigns": 1,
                    "storage_mb": 500
                },
                "description": "Perfect for trying out TrustCapture"
            },
            {
                "name": "pro",
                "display_name": "Pro",
                "price_inr_monthly": 999,
                "price_inr_yearly": 9990,
                "price_usd_monthly": 15,
                "price_usd_yearly": 150,
                "billing_cycles": ["monthly", "yearly"],
                "features": {
                    "photos_per_month": 1000,
                    "vendors": 10,
                    "campaigns": 5,
                    "storage_mb": 10240
                },
                "description": "For growing businesses with regular photo verification needs"
            },
            {
                "name": "enterprise",
                "display_name": "Enterprise",
                "price_inr_monthly": 4999,
                "price_inr_yearly": 49990,
                "price_usd_monthly": 75,
                "price_usd_yearly": 750,
                "billing_cycles": ["monthly", "yearly"],
                "features": {
                    "photos_per_month": "unlimited",
                    "vendors": "unlimited",
                    "campaigns": "unlimited",
                    "storage_mb": 102400
                },
                "description": "For large organizations with extensive verification requirements"
            }
        ]
    }


@router.get("/health")
async def subscription_health():
    """Health check endpoint for subscription service."""
    return {
        "status": "healthy",
        "service": "subscriptions",
        "endpoints": {
            "usage": "/api/subscriptions/usage",
            "current": "/api/subscriptions/current",
            "sync": "/api/subscriptions/sync-usage",
            "tiers": "/api/subscriptions/tiers"
        }
    }



# ============================================================================
# SUBSCRIPTION MANAGEMENT ENDPOINTS (Phase 4)
# ============================================================================

from pydantic import BaseModel
from app.services.subscription_manager import get_subscription_manager
from app.models.subscription import SubscriptionTier


class UpgradeRequest(BaseModel):
    """Request model for tier upgrade."""
    tier: str  # "pro" or "enterprise"
    billing_cycle: str = "monthly"  # "monthly" or "yearly"


class DowngradeRequest(BaseModel):
    """Request model for tier downgrade."""
    tier: str  # "free" or "pro"


class CancelRequest(BaseModel):
    """Request model for subscription cancellation."""
    immediate: bool = False  # If True, cancel immediately


class BillingCycleRequest(BaseModel):
    """Request model for billing cycle change."""
    billing_cycle: str  # "monthly" or "yearly"


@router.post("/upgrade")
async def upgrade_subscription(
    request: UpgradeRequest,
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Upgrade subscription to a higher tier.
    
    Upgrades take effect immediately and quotas are increased.
    Payment will be processed through the configured payment gateway.
    
    Requirements:
        - Req 11.1: Subscription management
        - Req 11.4: Tier upgrades
    """
    manager = get_subscription_manager(db)
    
    try:
        # Validate tier
        if request.tier not in ["pro", "enterprise"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only upgrade to 'pro' or 'enterprise' tier"
            )
        
        # Validate billing cycle
        if request.billing_cycle not in ["monthly", "yearly"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Billing cycle must be 'monthly' or 'yearly'"
            )
        
        new_tier = SubscriptionTier(request.tier)
        result = await manager.upgrade_tier(
            str(client.client_id),
            new_tier,
            request.billing_cycle
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upgrade subscription: {str(e)}"
        )


@router.post("/downgrade")
async def downgrade_subscription(
    request: DowngradeRequest,
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Downgrade subscription to a lower tier.
    
    Downgrades take effect at the end of the current billing period.
    Validates that current usage fits within new tier limits.
    
    Requirements:
        - Req 11.1: Subscription management
        - Req 11.5: Tier downgrades with validation
    """
    manager = get_subscription_manager(db)
    
    try:
        # Validate tier
        if request.tier not in ["free", "pro"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only downgrade to 'free' or 'pro' tier"
            )
        
        new_tier = SubscriptionTier(request.tier)
        result = await manager.downgrade_tier(
            str(client.client_id),
            new_tier
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to downgrade subscription: {str(e)}"
        )


@router.post("/cancel")
async def cancel_subscription(
    request: CancelRequest,
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel subscription.
    
    By default, cancellation takes effect at the end of the current billing period.
    Set immediate=true to cancel immediately and lose access right away.
    
    Requirements:
        - Req 11.1: Subscription management
        - Req 11.7: Cancellation workflow
    """
    manager = get_subscription_manager(db)
    
    try:
        result = await manager.cancel_subscription(
            str(client.client_id),
            request.immediate
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {str(e)}"
        )


@router.post("/reactivate")
async def reactivate_subscription(
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Reactivate a cancelled subscription.
    
    Restores access and resumes billing at the previous tier and rate.
    Only works for cancelled subscriptions.
    
    Requirements:
        - Req 11.1: Subscription management
        - Req 11.8: Reactivation
    """
    manager = get_subscription_manager(db)
    
    try:
        result = await manager.reactivate_subscription(str(client.client_id))
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reactivate subscription: {str(e)}"
        )


@router.post("/change-billing-cycle")
async def change_billing_cycle(
    request: BillingCycleRequest,
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Change billing cycle between monthly and yearly.
    
    Switching to yearly typically provides a discount.
    Change takes effect immediately and adjusts the next billing date.
    
    Requirements:
        - Req 11.1: Subscription management
        - Req 11.9: Billing cycle flexibility
    """
    manager = get_subscription_manager(db)
    
    try:
        result = await manager.change_billing_cycle(
            str(client.client_id),
            request.billing_cycle
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change billing cycle: {str(e)}"
        )
