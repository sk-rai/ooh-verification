"""summarize_analytics task handler."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from datetime import datetime, timezone, timedelta, date
from app.services.queue.registry import task_handler
from app.models.page_view import PageView, DailyAnalyticsSummary
import logging

logger = logging.getLogger(__name__)


@task_handler("summarize_analytics")
async def handle_summarize_analytics(db: AsyncSession, payload: dict):
    """Aggregate yesterday's page views and purge old raw data. Idempotent."""
    target_date_str = payload.get("target_date")
    if target_date_str:
        target_date = date.fromisoformat(target_date_str)
    else:
        target_date = (datetime.now(tz=timezone.utc) - timedelta(days=1)).date()

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)

    # Check if already summarized (idempotent)
    existing = await db.execute(
        select(DailyAnalyticsSummary).where(DailyAnalyticsSummary.date == target_date)
    )
    if existing.scalar_one_or_none():
        # Already done — just purge old data
        deleted = await db.execute(delete(PageView).where(PageView.created_at < cutoff))
        await db.commit()
        logger.info(f"Analytics already summarized for {target_date}, purged {deleted.rowcount} old records")
        return

    # Query raw data for target date
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    views = await db.execute(
        select(PageView).where(PageView.created_at >= day_start, PageView.created_at < day_end)
    )
    rows = views.scalars().all()

    if not rows:
        deleted = await db.execute(delete(PageView).where(PageView.created_at < cutoff))
        await db.commit()
        logger.info(f"No analytics data for {target_date}, purged {deleted.rowcount} old records")
        return

    # Aggregate
    total_views = len(rows)
    unique_visitors = len(set(r.visitor_hash for r in rows))
    unique_sessions = len(set(r.session_id for r in rows if r.session_id))
    registered_views = sum(1 for r in rows if r.is_registered_user)

    page_counts = {}
    ref_counts = {}
    country_counts = {}
    device_counts = {}
    browser_counts = {}
    utm_counts = {}

    for r in rows:
        page_counts[r.page] = page_counts.get(r.page, 0) + 1
        if r.referrer:
            ref_counts[r.referrer] = ref_counts.get(r.referrer, 0) + 1
        country_counts[r.country or "Unknown"] = country_counts.get(r.country or "Unknown", 0) + 1
        device_counts[r.device_type or "Unknown"] = device_counts.get(r.device_type or "Unknown", 0) + 1
        browser_counts[r.browser or "Unknown"] = browser_counts.get(r.browser or "Unknown", 0) + 1
        if r.utm_source:
            utm_counts[r.utm_source] = utm_counts.get(r.utm_source, 0) + 1

    summary = DailyAnalyticsSummary(
        date=target_date,
        total_views=total_views,
        unique_visitors=unique_visitors,
        unique_sessions=unique_sessions,
        registered_views=registered_views,
        top_pages=dict(sorted(page_counts.items(), key=lambda x: -x[1])[:20]),
        top_referrers=dict(sorted(ref_counts.items(), key=lambda x: -x[1])[:10]),
        countries=country_counts,
        devices=device_counts,
        browsers=browser_counts,
        utm_sources=utm_counts if utm_counts else None,
    )
    db.add(summary)

    deleted = await db.execute(delete(PageView).where(PageView.created_at < cutoff))
    await db.commit()
    logger.info(f"Summarized analytics for {target_date}: {total_views} views, purged {deleted.rowcount} old records")
