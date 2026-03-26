"""
Super Admin API endpoints.
Platform-level metrics and management - founder only.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case, text
from datetime import datetime, timedelta, timezone
import uuid

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.core.admin_deps import get_current_admin
from app.models.admin_user import AdminUser
from app.models.client import Client, SubscriptionTier, SubscriptionStatus
from app.models.vendor import Vendor
from app.models.campaign import Campaign
from app.models.campaign_vendor_assignment import CampaignVendorAssignment
from app.models.photo import Photo
from app.models.subscription import Subscription
from app.models.tenant_config import TenantConfig
from app.schemas.admin import (
    AdminLogin, AdminToken, AdminUserResponse,
    AdminDashboardResponse, PlatformOverview, ClientMetrics,
    TierBreakdown, SubscriptionBreakdown, SignupTrend,
    UsageMetrics, TopClient, RevenueMetrics, PhotoStats
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/login", response_model=AdminToken)
async def admin_login(
    data: AdminLogin,
    db: AsyncSession = Depends(get_db)
):
    """Admin login - returns JWT with type=admin."""
    result = await db.execute(
        select(AdminUser).where(AdminUser.email == data.email)
    )
    admin = result.scalar_one_or_none()

    if not admin or not verify_password(data.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )

    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is disabled"
        )

    # Update last login
    admin.last_login_at = datetime.now(tz=timezone.utc)
    await db.commit()

    access_token = create_access_token(
        data={
            "sub": str(admin.admin_id),
            "type": "admin",
            "email": admin.email
        }
    )

    return AdminToken(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", response_model=AdminUserResponse)
async def get_admin_profile(
    admin: AdminUser = Depends(get_current_admin)
):
    """Get current admin profile."""
    return admin


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def get_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Get comprehensive platform metrics for admin dashboard."""
    now = datetime.now(tz=timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    ninety_days_ago = now - timedelta(days=90)

    # ---- Platform Overview ----
    total_tenants = (await db.execute(
        select(func.count()).select_from(TenantConfig).where(TenantConfig.is_active == True)
    )).scalar() or 0

    total_clients = (await db.execute(
        select(func.count()).select_from(Client)
    )).scalar() or 0

    total_vendors = (await db.execute(
        select(func.count()).select_from(Vendor)
    )).scalar() or 0

    total_campaigns = (await db.execute(
        select(func.count()).select_from(Campaign)
    )).scalar() or 0

    total_assignments = (await db.execute(
        select(func.count()).select_from(CampaignVendorAssignment)
    )).scalar() or 0

    total_photos = 0
    try:
        total_photos = (await db.execute(
            select(func.count()).select_from(Photo)
        )).scalar() or 0
    except Exception:
        pass  # Photo table might not have data yet

    overview = PlatformOverview(
        total_tenants=total_tenants,
        total_clients=total_clients,
        total_vendors=total_vendors,
        total_campaigns=total_campaigns,
        total_assignments=total_assignments,
        total_photos=total_photos
    )

    # ---- Client Metrics ----
    # Tier breakdown
    tier_result = await db.execute(
        select(
            Client.subscription_tier,
            func.count(Client.client_id)
        ).group_by(Client.subscription_tier)
    )
    tier_counts = {row[0].value: row[1] for row in tier_result.all()}
    tier_breakdown = TierBreakdown(
        free=tier_counts.get("free", 0),
        pro=tier_counts.get("pro", 0),
        enterprise=tier_counts.get("enterprise", 0)
    )

    # Subscription status breakdown
    status_result = await db.execute(
        select(
            Client.subscription_status,
            func.count(Client.client_id)
        ).group_by(Client.subscription_status)
    )
    status_counts = {row[0].value: row[1] for row in status_result.all()}

    subscription_breakdown = SubscriptionBreakdown(
        active=status_counts.get("active", 0),
        cancelled=status_counts.get("cancelled", 0),
        expired=status_counts.get("expired", 0),
        past_due=status_counts.get("past_due", 0)
    )

    # Signups last 7 and 30 days
    signups_7d = (await db.execute(
        select(func.count()).select_from(Client).where(Client.created_at >= seven_days_ago)
    )).scalar() or 0

    signups_30d = (await db.execute(
        select(func.count()).select_from(Client).where(Client.created_at >= thirty_days_ago)
    )).scalar() or 0

    # Signup trend (last 30 days, grouped by date)
    trend_result = await db.execute(
        select(
            func.date_trunc('day', Client.created_at).label('day'),
            func.count(Client.client_id)
        ).where(
            Client.created_at >= thirty_days_ago
        ).group_by('day').order_by('day')
    )
    signup_trend = [
        SignupTrend(date=row[0].strftime('%Y-%m-%d'), count=row[1])
        for row in trend_result.all()
    ]

    client_metrics = ClientMetrics(
        total=total_clients,
        tier_breakdown=tier_breakdown,
        subscription_breakdown=subscription_breakdown,
        signups_last_7_days=signups_7d,
        signups_last_30_days=signups_30d,
        signup_trend=signup_trend
    )
    # ---- Usage Metrics ----
    # Build a subquery for vendor and campaign counts per client
    vendor_counts = (
        select(
            Vendor.created_by_client_id.label('client_id'),
            func.count(Vendor.vendor_id).label('vendors_count')
        ).group_by(Vendor.created_by_client_id)
    ).subquery()

    campaign_counts = (
        select(
            Campaign.client_id.label('client_id'),
            func.count(Campaign.campaign_id).label('campaigns_count'),
            func.max(Campaign.updated_at).label('last_campaign_activity')
        ).group_by(Campaign.client_id)
    ).subquery()

    # Heavy users: clients with most vendors + campaigns
    heavy_result = await db.execute(
        select(
            Client.client_id,
            Client.company_name,
            Client.email,
            Client.subscription_tier,
            Client.updated_at,
            func.coalesce(vendor_counts.c.vendors_count, 0).label('vc'),
            func.coalesce(campaign_counts.c.campaigns_count, 0).label('cc'),
        )
        .outerjoin(vendor_counts, Client.client_id == vendor_counts.c.client_id)
        .outerjoin(campaign_counts, Client.client_id == campaign_counts.c.client_id)
        .order_by(
            (func.coalesce(vendor_counts.c.vendors_count, 0) +
             func.coalesce(campaign_counts.c.campaigns_count, 0)).desc()
        )
        .limit(10)
    )
    heavy_users = [
        TopClient(
            client_id=str(r[0]), company_name=r[1], email=r[2],
            tier=r[3].value, last_active=r[4].isoformat() if r[4] else None,
            vendors_count=r[5], campaigns_count=r[6]
        ) for r in heavy_result.all()
    ]

    # Light users: clients with 0 or 1 vendors/campaigns, active subscription
    light_result = await db.execute(
        select(
            Client.client_id,
            Client.company_name,
            Client.email,
            Client.subscription_tier,
            Client.updated_at,
            func.coalesce(vendor_counts.c.vendors_count, 0).label('vc'),
            func.coalesce(campaign_counts.c.campaigns_count, 0).label('cc'),
        )
        .outerjoin(vendor_counts, Client.client_id == vendor_counts.c.client_id)
        .outerjoin(campaign_counts, Client.client_id == campaign_counts.c.client_id)
        .where(Client.subscription_status == SubscriptionStatus.ACTIVE)
        .order_by(
            (func.coalesce(vendor_counts.c.vendors_count, 0) +
             func.coalesce(campaign_counts.c.campaigns_count, 0)).asc()
        )
        .limit(10)
    )
    light_users = [
        TopClient(
            client_id=str(r[0]), company_name=r[1], email=r[2],
            tier=r[3].value, last_active=r[4].isoformat() if r[4] else None,
            vendors_count=r[5], campaigns_count=r[6]
        ) for r in light_result.all()
    ]
    # Inactive users: no updated_at activity in 90 days
    inactive_result = await db.execute(
        select(
            Client.client_id,
            Client.company_name,
            Client.email,
            Client.subscription_tier,
            Client.updated_at,
            func.coalesce(vendor_counts.c.vendors_count, 0).label('vc'),
            func.coalesce(campaign_counts.c.campaigns_count, 0).label('cc'),
        )
        .outerjoin(vendor_counts, Client.client_id == vendor_counts.c.client_id)
        .outerjoin(campaign_counts, Client.client_id == campaign_counts.c.client_id)
        .where(Client.updated_at < ninety_days_ago)
        .order_by(Client.updated_at.asc())
        .limit(10)
    )
    inactive_users = [
        TopClient(
            client_id=str(r[0]), company_name=r[1], email=r[2],
            tier=r[3].value, last_active=r[4].isoformat() if r[4] else None,
            vendors_count=r[5], campaigns_count=r[6]
        ) for r in inactive_result.all()
    ]

    # Recently active: clients with most recent updated_at
    recent_result = await db.execute(
        select(
            Client.client_id,
            Client.company_name,
            Client.email,
            Client.subscription_tier,
            Client.updated_at,
            func.coalesce(vendor_counts.c.vendors_count, 0).label('vc'),
            func.coalesce(campaign_counts.c.campaigns_count, 0).label('cc'),
        )
        .outerjoin(vendor_counts, Client.client_id == vendor_counts.c.client_id)
        .outerjoin(campaign_counts, Client.client_id == campaign_counts.c.client_id)
        .order_by(Client.updated_at.desc())
        .limit(10)
    )
    recently_active = [
        TopClient(
            client_id=str(r[0]), company_name=r[1], email=r[2],
            tier=r[3].value, last_active=r[4].isoformat() if r[4] else None,
            vendors_count=r[5], campaigns_count=r[6]
        ) for r in recent_result.all()
    ]

    usage = UsageMetrics(
        heavy_users=heavy_users,
        light_users=light_users,
        inactive_users=inactive_users,
        recently_active=recently_active
    )

    # ---- Revenue Metrics ----
    try:
        # Total revenue (sum of total_amount for active/cancelled paid subs)
        rev_inr = (await db.execute(
            select(func.coalesce(func.sum(Subscription.total_amount), 0))
            .where(Subscription.currency == 'INR', Subscription.total_amount > 0)
        )).scalar() or 0

        rev_usd = (await db.execute(
            select(func.coalesce(func.sum(Subscription.total_amount), 0))
            .where(Subscription.currency == 'USD', Subscription.total_amount > 0)
        )).scalar() or 0

        gst_collected = (await db.execute(
            select(func.coalesce(func.sum(Subscription.gst_amount), 0))
            .where(Subscription.gst_amount > 0)
        )).scalar() or 0

        pending_refunds_result = await db.execute(
            select(
                func.count(Subscription.subscription_id),
                func.coalesce(func.sum(Subscription.refund_amount), 0)
            ).where(Subscription.refund_status == 'pending')
        )
        pr_row = pending_refunds_result.one()
        pending_refund_count = pr_row[0] or 0
        pending_refund_amount = pr_row[1] or 0

        # MRR: sum of monthly-equivalent amounts for active paid subs
        mrr = (await db.execute(
            select(func.coalesce(func.sum(
                case(
                    (Subscription.billing_cycle == 'yearly', Subscription.total_amount / 12),
                    else_=Subscription.total_amount
                )
            ), 0))
            .where(Subscription.status == SubscriptionStatus.ACTIVE, Subscription.total_amount > 0)
        )).scalar() or 0

        paying = (await db.execute(
            select(func.count()).select_from(Subscription)
            .where(Subscription.total_amount > 0)
        )).scalar() or 0

        revenue = RevenueMetrics(
            total_revenue_inr=rev_inr, total_revenue_usd=rev_usd,
            total_gst_collected=gst_collected,
            pending_refunds=pending_refund_count,
            pending_refund_amount=pending_refund_amount,
            mrr_inr=int(mrr), paying_customers=paying
        )
    except Exception as e:
        logger.warning(f"Revenue metrics query failed: {e}")
        revenue = RevenueMetrics()

    # ---- Photo Verification Stats ----
    try:
        from app.models.photo import VerificationStatus
        photo_stats_result = await db.execute(
            select(
                Photo.verification_status,
                func.count(Photo.photo_id)
            ).group_by(Photo.verification_status)
        )
        photo_counts = {row[0].value if hasattr(row[0], 'value') else str(row[0]): row[1] for row in photo_stats_result.all()}

        total_storage = (await db.execute(
            select(func.coalesce(func.sum(Subscription.storage_used_mb), 0))
        )).scalar() or 0

        photo_stats = PhotoStats(
            total=sum(photo_counts.values()),
            verified=photo_counts.get('verified', 0),
            flagged=photo_counts.get('flagged', 0),
            rejected=photo_counts.get('rejected', 0) + photo_counts.get('failed', 0),
            pending=photo_counts.get('pending', 0),
            total_storage_mb=total_storage
        )
    except Exception as e:
        logger.warning(f"Photo stats query failed: {e}")
        photo_stats = PhotoStats(total=total_photos)

    return AdminDashboardResponse(
        overview=overview,
        clients=client_metrics,
        usage=usage,
        revenue=revenue,
        photos=photo_stats
    )
