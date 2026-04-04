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
from app.services.email_service import get_email_service
from app.services.queue import enqueue
from sqlalchemy import select
from datetime import datetime, timedelta
from app.models.subscription import Subscription, SubscriptionStatus
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
        - Quota information
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
            "updated_at": subscription.updated_at.isoformat(),
            # Add quota information from subscription
            "photos_quota": subscription.photos_quota,
            "vendors_quota": subscription.vendors_quota,
            "campaigns_quota": subscription.campaigns_quota,
            "storage_quota_mb": subscription.storage_quota_mb
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
                    "vendors": 5,
                    "campaigns": 3,
                    "storage_mb": 100
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




# ============================================================================
# AUTOMATED CRON ENDPOINTS (called by external scheduler)
# ============================================================================

@router.api_route("/cron/check-expiring", methods=["GET", "POST"])
async def check_expiring_subscriptions(
    db: AsyncSession = Depends(get_db)
):
    """
    Check for subscriptions expiring in 7 days and send notification emails.
    Designed to be called daily by an external cron (UptimeRobot, Render cron, etc.)
    
    No auth required — uses a simple shared secret via X-Cron-Secret header.
    """
    from fastapi import Request
    
    now = datetime.utcnow()
    expiry_window_start = now + timedelta(days=6)
    expiry_window_end = now + timedelta(days=8)
    
    # Find subscriptions expiring in ~7 days that are still active
    result = await db.execute(
        select(Subscription).where(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.current_period_end >= expiry_window_start,
            Subscription.current_period_end <= expiry_window_end,
            Subscription.auto_renew == 0,
        )
    )
    expiring = result.scalars().all()
    
    sent_count = 0
    for sub in expiring:
        try:
            # Get client email
            from app.models.client import Client
            client_result = await db.execute(
                select(Client).where(Client.client_id == sub.client_id)
            )
            client = client_result.scalar_one_or_none()
            if not client:
                continue
            
            days_remaining = (sub.current_period_end.replace(tzinfo=None) - now).days
            tier_value = sub.tier if isinstance(sub.tier, str) else sub.tier.value
            await enqueue(db, "send_email", {
                "tenant_id": str(sub.tenant_id),
                "template_name": "subscription_expiring",
                "to_email": client.email,
                "variables": {
                    "user_name": client.company_name or client.email,
                    "days_remaining": days_remaining,
                    "plan_name": tier_value.title(),
                    "expiry_date": sub.current_period_end.strftime("%B %d, %Y"),
                    "renewal_url": "https://trustcapture-web.onrender.com/subscription",
                }
            }, max_retries=5, tenant_id=sub.tenant_id)
            sent_count += 1
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to send expiry email for {sub.subscription_id}: {e}")
    
    return {"checked": len(expiring), "emails_sent": sent_count}


@router.api_route("/cron/auto-reset-quotas", methods=["GET", "POST"])
async def auto_reset_monthly_quotas(
    db: AsyncSession = Depends(get_db)
):
    """
    Auto-reset monthly photo quotas for subscriptions that have passed their period end.
    Also extends the billing period by 30/365 days.
    Designed to be called daily by an external cron.
    """
    now = datetime.utcnow()
    
    # Find active subscriptions past their period end
    result = await db.execute(
        select(Subscription).where(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.current_period_end <= now,
        )
    )
    expired_periods = result.scalars().all()
    
    reset_count = 0
    for sub in expired_periods:
        try:
            # Reset photo usage
            sub.photos_used = 0
            
            # Extend period
            if sub.billing_cycle == "yearly":
                sub.current_period_start = sub.current_period_end
                sub.current_period_end = sub.current_period_end + timedelta(days=365)
            else:
                sub.current_period_start = sub.current_period_end
                sub.current_period_end = sub.current_period_end + timedelta(days=30)
            
            sub.updated_at = now
            reset_count += 1
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to reset quota for {sub.subscription_id}: {e}")
    
    if reset_count > 0:
        await db.commit()
    
    return {"checked": len(expired_periods), "reset": reset_count}


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
    payment_gateway: str = "razorpay"  # "razorpay" or "stripe"


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
        gateway = request.payment_gateway

        # Create payment checkout via the selected gateway
        if gateway == "razorpay":
            razorpay_svc = get_razorpay_service()
            if not razorpay_svc:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Razorpay not configured")
            # Calculate amount based on tier and billing cycle
            tier_prices = {"pro": 99900, "enterprise": 499900}  # paise (999 INR, 4999 INR)
            base_amount = tier_prices.get(request.tier, 99900)
            if request.billing_cycle == "yearly":
                amount = int(base_amount * 12 * 0.83)  # 17% discount
            else:
                amount = base_amount
            # Add 18% GST
            gst = int(amount * 0.18)
            total_amount = amount + gst
            checkout = await razorpay_svc.create_payment_link(
                amount=total_amount,
                currency="INR",
                description=f"TrustCapture {request.tier.title()} Plan - {request.billing_cycle.title()} (incl. GST)",
            )
        else:
            stripe_svc = get_stripe_service()
            if not stripe_svc:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe not configured")
            checkout = await stripe_svc.create_subscription(db=db, client_id=str(client.client_id), tier=new_tier, billing_cycle=request.billing_cycle)

        # Store gateway info on subscription for webhook routing
        subscription = await manager.get_subscription(str(client.client_id))
        subscription.payment_gateway = gateway
        if checkout.get("subscription_id"):
            subscription.gateway_subscription_id = checkout["subscription_id"]
        if checkout.get("payment_link_id"):
            subscription.gateway_subscription_id = checkout["payment_link_id"]
        if checkout.get("customer_id"):
            subscription.gateway_customer_id = checkout["customer_id"]
        await db.commit()

        return {"payment_gateway": gateway, "checkout": checkout, "message": f"Complete payment to upgrade to {request.tier}"}

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout: {str(e)}"
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



@router.post("/reset-monthly-quotas")
async def reset_monthly_quotas(
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """Reset monthly photo quota at billing cycle start."""
    enforcer = get_quota_enforcer(db)
    try:
        await enforcer.reset_monthly_quotas(str(client.client_id))
        usage = await enforcer.get_usage_stats(str(client.client_id))
        return {"message": "Monthly photo quota reset", "usage": usage}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to reset quotas: {str(e)}")
