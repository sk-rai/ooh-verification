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


@router.get("/analytics")
async def get_analytics_dashboard(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Get visitor analytics for admin dashboard."""
    from app.models.page_view import PageView, DailyAnalyticsSummary
    from datetime import date as date_type

    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(days=days)

    # Today's live data from raw page_views
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    today_result = await db.execute(
        select(
            func.count(PageView.id).label('views'),
            func.count(func.distinct(PageView.visitor_hash)).label('visitors'),
        ).where(PageView.created_at >= today_start)
    )
    today = today_result.one()

    # Historical summaries
    summaries = await db.execute(
        select(DailyAnalyticsSummary)
        .where(DailyAnalyticsSummary.date >= cutoff.date())
        .order_by(DailyAnalyticsSummary.date.desc())
    )
    summary_rows = summaries.scalars().all()

    # Aggregate totals from summaries
    total_views = sum(s.total_views for s in summary_rows) + (today[0] or 0)
    total_visitors = sum(s.unique_visitors for s in summary_rows) + (today[1] or 0)

    # Aggregate top pages across all summaries
    all_pages = {}
    for s in summary_rows:
        if s.top_pages:
            for page, count in s.top_pages.items():
                all_pages[page] = all_pages.get(page, 0) + count

    # Aggregate countries
    all_countries = {}
    for s in summary_rows:
        if s.countries:
            for c, count in s.countries.items():
                all_countries[c] = all_countries.get(c, 0) + count

    # Aggregate devices
    all_devices = {}
    for s in summary_rows:
        if s.devices:
            for d, count in s.devices.items():
                all_devices[d] = all_devices.get(d, 0) + count

    # Aggregate browsers
    all_browsers = {}
    for s in summary_rows:
        if s.browsers:
            for b, count in s.browsers.items():
                all_browsers[b] = all_browsers.get(b, 0) + count

    # Daily trend
    daily_trend = [
        {"date": s.date.isoformat(), "views": s.total_views, "visitors": s.unique_visitors}
        for s in sorted(summary_rows, key=lambda x: x.date)
    ]

    # Add today
    daily_trend.append({
        "date": now.date().isoformat(),
        "views": today[0] or 0,
        "visitors": today[1] or 0,
    })

    return {
        "period_days": days,
        "today": {"views": today[0] or 0, "visitors": today[1] or 0},
        "total": {"views": total_views, "visitors": total_visitors},
        "daily_trend": daily_trend,
        "top_pages": dict(sorted(all_pages.items(), key=lambda x: -x[1])[:20]),
        "countries": dict(sorted(all_countries.items(), key=lambda x: -x[1])[:20]),
        "devices": all_devices,
        "browsers": all_browsers,
    }


@router.get("/clients/{client_id}")
async def get_client_detail(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Get full client detail including subscription, vendors, campaigns."""
    from app.models.vendor import Vendor
    from app.models.campaign import Campaign
    from app.models.subscription import Subscription
    from app.models.photo import Photo

    # Client
    result = await db.execute(select(Client).where(Client.client_id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Subscription
    sub_result = await db.execute(select(Subscription).where(Subscription.client_id == client_id))
    sub = sub_result.scalar_one_or_none()

    # Counts
    vendor_count = (await db.execute(
        select(func.count(Vendor.vendor_id)).where(Vendor.created_by_client_id == client_id)
    )).scalar() or 0

    campaign_count = (await db.execute(
        select(func.count(Campaign.campaign_id)).where(Campaign.client_id == client_id)
    )).scalar() or 0

    photo_count = (await db.execute(
        select(func.count(Photo.photo_id)).where(Photo.tenant_id == client.tenant_id)
    )).scalar() or 0

    # Recent vendors
    vendors_result = await db.execute(
        select(Vendor).where(Vendor.created_by_client_id == client_id).order_by(Vendor.created_at.desc()).limit(10)
    )
    vendors = vendors_result.scalars().all()

    # Recent campaigns
    campaigns_result = await db.execute(
        select(Campaign).where(Campaign.client_id == client_id).order_by(Campaign.created_at.desc()).limit(10)
    )
    campaigns = campaigns_result.scalars().all()

    return {
        "client": {
            "client_id": str(client.client_id),
            "email": client.email,
            "company_name": client.company_name,
            "phone_number": client.phone_number,
            "contact_person": getattr(client, 'contact_person', None),
            "contact_phone": getattr(client, 'contact_phone', None),
            "title": getattr(client, 'title', None),
            "designation": getattr(client, 'designation', None),
            "address": getattr(client, 'address', None),
            "city": getattr(client, 'city', None),
            "state": getattr(client, 'state', None),
            "country": getattr(client, 'country', None),
            "website": getattr(client, 'website', None),
            "industry": getattr(client, 'industry', None),
            "subscription_tier": client.subscription_tier.value if hasattr(client.subscription_tier, 'value') else str(client.subscription_tier),
            "subscription_status": client.subscription_status.value if hasattr(client.subscription_status, 'value') else str(client.subscription_status),
            "created_at": client.created_at.isoformat() if client.created_at else None,
        },
        "subscription": {
            "tier": sub.tier.value if sub and hasattr(sub.tier, 'value') else (sub.tier if sub else 'free'),
            "status": sub.status.value if sub and hasattr(sub.status, 'value') else (sub.status if sub else 'active'),
            "billing_cycle": sub.billing_cycle if sub else 'monthly',
            "amount": sub.amount if sub else 0,
            "currency": sub.currency if sub else 'INR',
            "base_amount": sub.base_amount if sub else None,
            "gst_amount": sub.gst_amount if sub else None,
            "photos_quota": sub.photos_quota if sub else 50,
            "photos_used": sub.photos_used if sub else 0,
            "vendors_quota": sub.vendors_quota if sub else 5,
            "vendors_used": sub.vendors_used if sub else 0,
            "campaigns_quota": sub.campaigns_quota if sub else 3,
            "campaigns_used": sub.campaigns_used if sub else 0,
            "storage_quota_mb": sub.storage_quota_mb if sub else 100,
            "storage_used_mb": sub.storage_used_mb if sub else 0,
            "current_period_end": sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
            "refund_status": sub.refund_status if sub else None,
            "refund_amount": sub.refund_amount if sub else None,
        } if sub else None,
        "counts": {
            "vendors": vendor_count,
            "campaigns": campaign_count,
            "photos": photo_count,
        },
        "recent_vendors": [
            {"vendor_id": v.vendor_id, "name": v.name, "phone": v.phone_number, "status": v.status.value if hasattr(v.status, 'value') else str(v.status), "city": getattr(v, 'city', None)}
            for v in vendors
        ],
        "recent_campaigns": [
            {"campaign_id": str(c.campaign_id), "name": c.name, "code": c.campaign_code, "status": c.status.value if hasattr(c.status, 'value') else str(c.status)}
            for c in campaigns
        ],
    }


@router.post("/fix-quotas")
async def fix_quotas(db: AsyncSession = Depends(get_db)):
    """One-time fix: bump free tier campaign quota to 10."""
    from sqlalchemy import text
    result = await db.execute(text("UPDATE subscriptions SET campaigns_quota = 10 WHERE campaigns_quota <= 3"))
    await db.commit()
    return {"updated": result.rowcount, "new_quota": 10}


@router.post("/fix-location-constraint")
async def fix_location_constraint(db: AsyncSession = Depends(get_db)):
    """Drop unique constraint on location_profiles.campaign_id for multi-location support."""
    from sqlalchemy import text
    results = []
    # Try all possible constraint names
    for name in ['location_profiles_campaign_id_key', 'uq_location_profiles_campaign_id', 'location_profiles_campaign_id_idx']:
        try:
            await db.execute(text(f"ALTER TABLE location_profiles DROP CONSTRAINT IF EXISTS {name}"))
            results.append(f"Dropped {name}")
        except Exception as e:
            results.append(f"Skip {name}: {e}")
    # Also try dropping unique index
    try:
        await db.execute(text("DROP INDEX IF EXISTS location_profiles_campaign_id_key"))
        results.append("Dropped index location_profiles_campaign_id_key")
    except Exception as e:
        results.append(f"Skip index drop: {e}")
    # Create non-unique index
    try:
        await db.execute(text("CREATE INDEX IF NOT EXISTS ix_location_profiles_campaign_id ON location_profiles (campaign_id)"))
        results.append("Created non-unique index")
    except Exception as e:
        results.append(f"Skip index create: {e}")
    await db.commit()
    return {"results": results}


@router.post("/fix-duplicate-locations")
async def fix_duplicate_locations(db: AsyncSession = Depends(get_db)):
    """Remove duplicate location profiles (keep first of each unique lat/lon per campaign)."""
    from sqlalchemy import text
    result = await db.execute(text("""
        DELETE FROM location_profiles
        WHERE profile_id NOT IN (
            SELECT DISTINCT ON (campaign_id, expected_latitude, expected_longitude)
            profile_id FROM location_profiles
            ORDER BY campaign_id, expected_latitude, expected_longitude, created_at ASC
        )
    """))
    await db.commit()
    return {"duplicates_removed": result.rowcount}


@router.post("/fix-otp-table")
async def fix_otp_table(db: AsyncSession = Depends(get_db)):
    """Create otp_codes table if not exists."""
    from sqlalchemy import text
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS otp_codes (
            phone_number VARCHAR(20) PRIMARY KEY,
            otp VARCHAR(10) NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT now()
        );
    """))
    await db.commit()
    return {"status": "otp_codes table ready"}


@router.post("/fix-tolerance")
async def fix_tolerance(db: AsyncSession = Depends(get_db)):
    """Update all location profiles with tolerance <= 1000m to 1500m."""
    from sqlalchemy import text
    result = await db.execute(text(
        "UPDATE location_profiles SET tolerance_meters = 1500 WHERE tolerance_meters <= 1000"
    ))
    await db.commit()
    return {"updated": result.rowcount, "new_tolerance": 1500}


@router.post("/create-review-vendor")
async def create_review_vendor(db: AsyncSession = Depends(get_db)):
    """Create the Play Store review test vendor."""
    from sqlalchemy import text
    # Get default tenant
    tenant_result = await db.execute(text("SELECT tenant_id FROM tenants LIMIT 1"))
    tenant = tenant_result.fetchone()
    if not tenant:
        return {"error": "No tenant found"}
    tenant_id = str(tenant[0])
    
    # Create vendor
    await db.execute(text("""
        INSERT INTO vendors (vendor_id, tenant_id, name, phone_number, status, device_verified, created_at, updated_at)
        VALUES ('REVIEW', :tid, 'Play Store Reviewer', '+911234567890', 'active', true, now(), now())
        ON CONFLICT (vendor_id) DO UPDATE SET phone_number = '+911234567890', status = 'active', device_verified = true
    """), {"tid": tenant_id})
    await db.commit()
    return {"status": "REVIEW vendor created", "vendor_id": "REVIEW", "phone": "+911234567890"}

