"""
GPS Tracking API — passive location tracking for vendor attendance proof.

Endpoints:
- POST /api/tracks/sync — Android sends batch of GPS points
- GET /api/tracks/vendor/{vendor_id}?date= — Get vendor's track for a day
- GET /api/tracks/summary?start_date=&end_date= — Attendance summary
"""
import math
from datetime import datetime, date, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, cast, Date
from uuid import UUID

from app.core.database import get_db
from app.core.deps import get_current_active_vendor, get_current_client
from app.models.vendor import Vendor
from app.models.client import Client
from app.models.vendor_track import VendorTrack
from app.models.campaign import Campaign
from app.models.campaign_vendor_assignment import CampaignVendorAssignment
from app.middleware.tenant_context import get_current_tenant

import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tracks", tags=["tracking"])


# --------------------------------------------------------------------------- #
# Client-entitlement predicates for vendor tracks (read endpoints only)
#
# Rule (owner-confirmed, date-bounded campaign scope with orphan fallback).
# A track (vendor V, date D) is visible to client C iff:
#   1. IN-WINDOW: C owns a campaign assigned to V whose [start_date, end_date]
#      covers D (inclusive both ends); OR
#   2. ORPHAN FALLBACK: NO client has such a covering campaign for (V, D) AND
#      C created V (vendors.created_by_client_id == C).
# If two clients both have covering campaigns, both are entitled (accepted
# overlap behavior; no assignment constraint is introduced). An in-window
# assignment suppresses the home-client orphan fallback for that day.
#
# Safety properties:
#   * Every predicate is correlated to the CANDIDATE VendorTrack row (vendor_id,
#     track_date, tenant_id) so entitlement is evaluated per row.
#   * Strict tenant correlation: campaigns and vendors consulted must carry the
#     same tenant_id as the candidate VendorTrack. campaign_vendor_assignments has
#     no tenant_id, so the tenant is enforced via the joined Campaign and Vendor.
#   * Campaign bounds are timestamptz; they are converted to a DATE explicitly in
#     UTC (timezone('UTC', ts)::date) so the result never depends on the
#     PostgreSQL session TimeZone setting.
# --------------------------------------------------------------------------- #
def _utc_date(column):
    """timestamptz -> DATE in UTC, independent of the session timezone."""
    return cast(func.timezone("UTC", column), Date)


def _covering_campaign_exists(client_id=None):
    """EXISTS(a campaign assignment covering the candidate VendorTrack's day).

    Correlated to the enclosing VendorTrack row. When client_id is given, only
    that client's campaigns count; otherwise any client's campaign counts.
    """
    conditions = [
        CampaignVendorAssignment.vendor_id == VendorTrack.vendor_id,
        # strict tenant correlation: campaign + vendor must match the track's tenant
        Campaign.tenant_id == VendorTrack.tenant_id,
        Vendor.tenant_id == VendorTrack.tenant_id,
        # inclusive UTC date window
        VendorTrack.track_date >= _utc_date(Campaign.start_date),
        VendorTrack.track_date <= _utc_date(Campaign.end_date),
    ]
    if client_id is not None:
        conditions.append(Campaign.client_id == client_id)
    return (
        select(1)
        .select_from(CampaignVendorAssignment)
        .join(Campaign, Campaign.campaign_id == CampaignVendorAssignment.campaign_id)
        .join(Vendor, Vendor.vendor_id == CampaignVendorAssignment.vendor_id)
        .where(*conditions)
        .exists()
    )


def _in_window_for_client(client_id):
    """C owns a campaign assigned to V that covers D (same tenant)."""
    return _covering_campaign_exists(client_id)


def _covered_by_any_client():
    """SOME client has a campaign assigned to V that covers D (same tenant)."""
    return _covering_campaign_exists(None)


def _created_by_client(client_id):
    """C created the candidate track's vendor, resolved within the same tenant."""
    return (
        select(1)
        .select_from(Vendor)
        .where(
            Vendor.vendor_id == VendorTrack.vendor_id,
            Vendor.tenant_id == VendorTrack.tenant_id,
            Vendor.created_by_client_id == client_id,
        )
        .exists()
    )


def _visible_to(client_id):
    """Entitlement predicate over the candidate VendorTrack row for client C."""
    return _in_window_for_client(client_id) | and_(
        ~_covered_by_any_client(),
        _created_by_client(client_id),
    )


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in meters between two GPS points."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_track_stats(points: List[dict]) -> dict:
    """Compute distance, start/end time from points array."""
    if not points:
        return {"distance": 0, "start_time": None, "end_time": None, "duration": 0}

    sorted_points = sorted(points, key=lambda p: p.get("timestamp_ms", 0))

    total_dist = 0.0
    for i in range(1, len(sorted_points)):
        p1, p2 = sorted_points[i - 1], sorted_points[i]
        lat1, lon1 = p1.get("lat", 0), p1.get("lon", 0)
        lat2, lon2 = p2.get("lat", 0), p2.get("lon", 0)
        if lat1 and lon1 and lat2 and lon2:
            total_dist += haversine(lat1, lon1, lat2, lon2)

    first_ts = sorted_points[0].get("timestamp_ms")
    last_ts = sorted_points[-1].get("timestamp_ms")

    start_time = datetime.utcfromtimestamp(first_ts / 1000) if first_ts else None
    end_time = datetime.utcfromtimestamp(last_ts / 1000) if last_ts else None
    duration = (last_ts - first_ts) / 1000.0 if first_ts and last_ts else 0

    return {"distance": total_dist, "start_time": start_time, "end_time": end_time, "duration": duration}


class TrackSyncRequest(BaseModel):
    """Request body for syncing GPS points."""
    points: List[dict] = Field(..., description="Array of {lat, lon, accuracy, timestamp_ms, battery_pct}")
    campaign_id: Optional[str] = Field(None, description="Optional campaign context")


@router.post("/sync")
async def sync_track(
    data: TrackSyncRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    vendor: Vendor = Depends(get_current_active_vendor),
):
    """
    Sync GPS track points from Android.

    Android sends batch of GPS points periodically.
    Points are appended to today's track record (upsert).
    """
    tenant_id = get_current_tenant(request)

    if not data.points:
        return {"status": "no_points", "points_received": 0}

    today = date.today()

    # Find or create today's track
    result = await db.execute(
        select(VendorTrack).where(
            VendorTrack.vendor_id == vendor.vendor_id,
            VendorTrack.track_date == today,
        )
    )
    track = result.scalar_one_or_none()

    if track:
        # Append points
        existing_points = track.points or []
        existing_points.extend(data.points)
        track.points = existing_points
        track.point_count = len(existing_points)
    else:
        # Create new track for today
        track = VendorTrack(
            tenant_id=tenant_id,
            vendor_id=vendor.vendor_id,
            track_date=today,
            points=data.points,
            point_count=len(data.points),
            status="active",
        )
        db.add(track)

    # Recompute stats
    stats = compute_track_stats(track.points)
    track.total_distance_meters = stats["distance"]
    track.start_time = stats["start_time"]
    track.end_time = stats["end_time"]
    track.duration_seconds = stats["duration"]

    await db.commit()
    await db.refresh(track)

    return {
        "status": "synced",
        "track_id": str(track.track_id),
        "points_received": len(data.points),
        "total_points_today": track.point_count,
        "distance_km": round((track.total_distance_meters or 0) / 1000, 2),
    }


@router.get("/vendor/{vendor_id}")
async def get_vendor_track(
    vendor_id: str,
    track_date: str = Query(..., alias="date", description="Date (YYYY-MM-DD)"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    """Get a vendor's GPS track for a specific day."""
    tenant_id = get_current_tenant(request)

    try:
        query_date = datetime.fromisoformat(track_date).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Tenant match is defense-in-depth; _visible_to enforces client entitlement for
    # this exact (vendor, date). Not entitled -> same empty shape as "no track"
    # (never a 404), so a client cannot probe another client's vendor.
    result = await db.execute(
        select(VendorTrack).where(
            VendorTrack.tenant_id == tenant_id,
            VendorTrack.vendor_id == vendor_id,
            VendorTrack.track_date == query_date,
            _visible_to(client.client_id),
        )
    )
    track = result.scalar_one_or_none()

    if not track:
        return {"vendor_id": vendor_id, "date": track_date, "points": [], "stats": None}

    return {
        "vendor_id": vendor_id,
        "date": track_date,
        "track_id": str(track.track_id),
        "points": track.points or [],
        "point_count": track.point_count,
        "stats": {
            "distance_km": round((track.total_distance_meters or 0) / 1000, 2),
            "start_time": track.start_time.isoformat() if track.start_time else None,
            "end_time": track.end_time.isoformat() if track.end_time else None,
            "duration_hours": round((track.duration_seconds or 0) / 3600, 2),
        },
    }


@router.get("/summary")
async def get_tracking_summary(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    """Get attendance summary for all vendors in date range."""
    tenant_id = get_current_tenant(request)

    try:
        start_dt = datetime.fromisoformat(start_date).date()
        end_dt = datetime.fromisoformat(end_date).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    result = await db.execute(
        select(VendorTrack).where(
            VendorTrack.tenant_id == tenant_id,
            VendorTrack.track_date >= start_dt,
            VendorTrack.track_date <= end_dt,
            _visible_to(client.client_id),
        ).order_by(VendorTrack.track_date.desc())
    )
    tracks = result.scalars().all()

    # Get vendor names
    vendor_ids = list(set(t.vendor_id for t in tracks))
    if vendor_ids:
        vendor_result = await db.execute(
            select(Vendor).where(Vendor.vendor_id.in_(vendor_ids))
        )
        vendors = {v.vendor_id: v for v in vendor_result.scalars().all()}
    else:
        vendors = {}

    rows = []
    for track in tracks:
        vendor = vendors.get(track.vendor_id)
        rows.append({
            "date": track.track_date.isoformat(),
            "vendor_id": track.vendor_id,
            "vendor_name": vendor.name if vendor else "",
            "vendor_phone": vendor.phone_number if vendor else "",
            "point_count": track.point_count,
            "distance_km": round((track.total_distance_meters or 0) / 1000, 2),
            "start_time": track.start_time.strftime("%H:%M:%S") if track.start_time else None,
            "end_time": track.end_time.strftime("%H:%M:%S") if track.end_time else None,
            "duration_hours": round((track.duration_seconds or 0) / 3600, 2),
            "status": track.status,
        })

    return {
        "period": {"start": start_date, "end": end_date},
        "total_vendors": len(vendor_ids),
        "total_tracks": len(tracks),
        "rows": rows,
    }


@router.get("/me")
async def get_my_track(
    track_date: str = Query(None, alias="date", description="Date YYYY-MM-DD, defaults to today"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    vendor: Vendor = Depends(get_current_active_vendor),
):
    """Get current vendor own GPS track. Used by Android My Route Today screen."""
    if track_date:
        try:
            query_date = datetime.fromisoformat(track_date).date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        query_date = date.today()

    result = await db.execute(
        select(VendorTrack).where(
            VendorTrack.vendor_id == vendor.vendor_id,
            VendorTrack.track_date == query_date,
        )
    )
    track = result.scalar_one_or_none()

    if not track:
        return {"vendor_id": vendor.vendor_id, "date": str(query_date), "points": [], "stats": None}

    return {
        "vendor_id": vendor.vendor_id,
        "date": str(query_date),
        "track_id": str(track.track_id),
        "points": track.points or [],
        "point_count": track.point_count,
        "stats": {
            "distance_km": round((track.total_distance_meters or 0) / 1000, 2),
            "start_time": track.start_time.isoformat() if track.start_time else None,
            "end_time": track.end_time.isoformat() if track.end_time else None,
            "duration_hours": round((track.duration_seconds or 0) / 3600, 2),
        },
    }
