"""
Visitor analytics API.
- POST /track: log a page view (called from frontend)
- GET /admin/analytics: dashboard data (admin only)
- GET /cron/summarize-analytics: daily summarize + purge
"""
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, and_, cast, Date
from datetime import datetime, timedelta, timezone, date
from typing import Optional
import hashlib
import logging

from app.core.database import get_db
from app.models.page_view import PageView, DailyAnalyticsSummary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def parse_user_agent(ua: str) -> dict:
    """Simple user-agent parser — no external deps."""
    ua_lower = ua.lower()
    # Device
    if any(k in ua_lower for k in ['mobile', 'android', 'iphone', 'ipad']):
        device = 'tablet' if 'ipad' in ua_lower else 'mobile'
    else:
        device = 'desktop'
    # Browser
    if 'edg' in ua_lower:
        browser = 'Edge'
    elif 'chrome' in ua_lower and 'safari' in ua_lower:
        browser = 'Chrome'
    elif 'firefox' in ua_lower:
        browser = 'Firefox'
    elif 'safari' in ua_lower:
        browser = 'Safari'
    else:
        browser = 'Other'
    # OS
    if 'windows' in ua_lower:
        os_name = 'Windows'
    elif 'mac' in ua_lower:
        os_name = 'macOS'
    elif 'linux' in ua_lower:
        os_name = 'Linux'
    elif 'android' in ua_lower:
        os_name = 'Android'
    elif 'iphone' in ua_lower or 'ipad' in ua_lower:
        os_name = 'iOS'
    else:
        os_name = 'Other'
    return {'device': device, 'browser': browser, 'os': os_name}


def get_visitor_hash(ip: str, ua: str) -> str:
    """Create anonymous daily-rotating visitor hash. No PII stored."""
    today = date.today().isoformat()
    raw = f"{ip}:{ua}:{today}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


from pydantic import BaseModel

class TrackEvent(BaseModel):
    page: str
    referrer: Optional[str] = None
    session_id: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


@router.post("/track")
async def track_page_view(
    event: TrackEvent,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Track a page view. Called from frontend on each navigation."""
    try:
        ip = request.client.host if request.client else "unknown"
        ua = request.headers.get("user-agent", "")
        visitor_hash = get_visitor_hash(ip, ua)
        ua_info = parse_user_agent(ua)

        # Get tenant from request state if available
        tenant_id = getattr(request.state, 'tenant_id', None)

        pv = PageView(
            visitor_hash=visitor_hash,
            session_id=event.session_id,
            page=event.page[:500],
            referrer=(event.referrer or "")[:1000] or None,
            device_type=ua_info['device'],
            browser=ua_info['browser'],
            os=ua_info['os'],
            utm_source=event.utm_source,
            utm_medium=event.utm_medium,
            utm_campaign=event.utm_campaign,
            tenant_id=tenant_id,
        )
        db.add(pv)
        await db.commit()
        return {"status": "ok"}
    except Exception as e:
        logger.warning(f"Analytics track failed: {e}")
        return {"status": "ok"}  # Never fail the user experience


@router.api_route("/cron/summarize", methods=["GET", "POST"])
async def summarize_and_purge(db: AsyncSession = Depends(get_db)):
    """
    Daily cron: summarize yesterday's data into daily_analytics_summary,
    then purge raw page_views older than 30 days.
    """
    yesterday = (datetime.now(tz=timezone.utc) - timedelta(days=1)).date()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)

    try:
        # Check if summary already exists for yesterday
        existing = await db.execute(
            select(DailyAnalyticsSummary).where(DailyAnalyticsSummary.date == yesterday)
        )
        if existing.scalar_one_or_none():
            # Already summarized, just purge old data
            deleted = await db.execute(
                delete(PageView).where(PageView.created_at < cutoff)
            )
            await db.commit()
            return {"summarized": False, "purged": deleted.rowcount, "reason": "already summarized"}

        # Query yesterday's raw data
        day_start = datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        views = await db.execute(
            select(PageView).where(
                PageView.created_at >= day_start,
                PageView.created_at < day_end,
            )
        )
        rows = views.scalars().all()

        if not rows:
            # No data yesterday, still purge old
            deleted = await db.execute(delete(PageView).where(PageView.created_at < cutoff))
            await db.commit()
            return {"summarized": False, "purged": deleted.rowcount, "reason": "no data yesterday"}

        # Aggregate
        total_views = len(rows)
        unique_visitors = len(set(r.visitor_hash for r in rows))
        unique_sessions = len(set(r.session_id for r in rows if r.session_id))
        registered_views = sum(1 for r in rows if r.is_registered_user)

        # Top pages
        page_counts = {}
        for r in rows:
            page_counts[r.page] = page_counts.get(r.page, 0) + 1
        top_pages = dict(sorted(page_counts.items(), key=lambda x: -x[1])[:20])

        # Top referrers
        ref_counts = {}
        for r in rows:
            if r.referrer:
                ref_counts[r.referrer] = ref_counts.get(r.referrer, 0) + 1
        top_referrers = dict(sorted(ref_counts.items(), key=lambda x: -x[1])[:10])

        # Countries
        country_counts = {}
        for r in rows:
            c = r.country or 'Unknown'
            country_counts[c] = country_counts.get(c, 0) + 1

        # Devices
        device_counts = {}
        for r in rows:
            d = r.device_type or 'Unknown'
            device_counts[d] = device_counts.get(d, 0) + 1

        # Browsers
        browser_counts = {}
        for r in rows:
            b = r.browser or 'Unknown'
            browser_counts[b] = browser_counts.get(b, 0) + 1

        # UTM sources
        utm_counts = {}
        for r in rows:
            if r.utm_source:
                utm_counts[r.utm_source] = utm_counts.get(r.utm_source, 0) + 1

        summary = DailyAnalyticsSummary(
            date=yesterday,
            total_views=total_views,
            unique_visitors=unique_visitors,
            unique_sessions=unique_sessions,
            registered_views=registered_views,
            top_pages=top_pages,
            top_referrers=top_referrers,
            countries=country_counts,
            devices=device_counts,
            browsers=browser_counts,
            utm_sources=utm_counts if utm_counts else None,
        )
        db.add(summary)

        # Purge old raw data
        deleted = await db.execute(delete(PageView).where(PageView.created_at < cutoff))
        await db.commit()

        return {"summarized": True, "date": str(yesterday), "views": total_views, "purged": deleted.rowcount}

    except Exception as e:
        logger.error(f"Analytics summarize failed: {e}")
        return {"error": str(e)}
