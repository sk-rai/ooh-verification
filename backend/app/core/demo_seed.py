"""
One-time demo tracking seeder (guarded).

Purpose: populate the GPS Tracking screen with a realistic route + attendance
for a single real vendor under the lynksavvy account, for a product demo video.

SAFETY / CONTROL:
- Runs ONLY when the environment variable SEED_DEMO_TRACKS == "1".
- Fully idempotent: upserts on vendor_tracks (vendor_id, track_date).
- Never raises — any failure is logged and swallowed so it cannot affect boot.
- Touches ONLY the vendor_tracks table (demo data). No other tables modified.

Intended lifecycle: set SEED_DEMO_TRACKS=1 for ONE deploy to seed prod, capture
the demo, then unset the variable (and this module can be removed in a follow-up
commit). The seeded rows can be deleted later via delete_demo_tracks().
"""
import os
import math
import json
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

logger = logging.getLogger(__name__)

# Realistic street-level Mumbai routes (lat, lon). Street-level so the Leaflet
# map auto-zooms to a recognizable route rather than the whole-India view.
_ROUTES = {
    "bandra": [
        (19.0596, 72.8295), (19.0612, 72.8331), (19.0648, 72.8356),
        (19.0689, 72.8372), (19.0725, 72.8401), (19.0767, 72.8419),
        (19.0808, 72.8438), (19.0841, 72.8467), (19.0876, 72.8492),
        (19.0902, 72.8521),
    ],
    "andheri": [
        (19.1136, 72.8697), (19.1159, 72.8721), (19.1182, 72.8749),
        (19.1207, 72.8773), (19.1234, 72.8798), (19.1258, 72.8822),
        (19.1281, 72.8849), (19.1303, 72.8875), (19.1327, 72.8901),
    ],
    "worli": [
        (18.9960, 72.8302), (18.9987, 72.8276), (19.0021, 72.8251),
        (19.0058, 72.8229), (19.0094, 72.8207), (19.0128, 72.8184),
        (19.0163, 72.8162), (19.0199, 72.8140),
    ],
}


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _build_points(waypoints, day: date, start_hour: int):
    pts = []
    t0 = datetime(day.year, day.month, day.day, start_hour, 0, 0, tzinfo=timezone.utc)
    battery = 98
    for i, (lat, lon) in enumerate(waypoints):
        ts = t0 + timedelta(minutes=6 * i)
        battery = max(20, battery - 2)
        pts.append({
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "accuracy": 8 + (i % 3) * 2,
            "timestamp_ms": int(ts.timestamp() * 1000),
            "battery_pct": battery,
        })
    return pts


def _stats(points):
    sp = sorted(points, key=lambda p: p["timestamp_ms"])
    dist = 0.0
    for i in range(1, len(sp)):
        dist += _haversine(sp[i-1]["lat"], sp[i-1]["lon"], sp[i]["lat"], sp[i]["lon"])
    first = datetime.fromtimestamp(sp[0]["timestamp_ms"] / 1000, tz=timezone.utc)
    last = datetime.fromtimestamp(sp[-1]["timestamp_ms"] / 1000, tz=timezone.utc)
    return dist, first, last, (last - first).total_seconds()


async def _resolve_vendor(conn):
    """Pick one active vendor under the lynksavvy account. Returns (vendor_id, tenant_id) or (None, None)."""
    row = (await conn.execute(text(
        """
        SELECT v.vendor_id, v.tenant_id
        FROM vendors v
        JOIN clients c ON c.client_id = v.created_by_client_id
        WHERE (c.email ILIKE '%lynksavvy%' OR c.company_name ILIKE '%lynksavvy%'
               OR c.email ILIKE '%rai_sk%')
          AND v.status = 'active'
        ORDER BY v.created_at
        LIMIT 1
        """
    ))).fetchone()
    if row:
        return row[0], str(row[1])
    return None, None


async def seed_demo_tracks(engine) -> None:
    """Idempotently seed demo GPS tracks for one lynksavvy vendor. Guarded + safe."""
    if os.getenv("SEED_DEMO_TRACKS") != "1":
        return
    try:
        async with engine.begin() as conn:
            vendor_id, tenant_id = await _resolve_vendor(conn)
            if not vendor_id:
                logger.warning("[demo_seed] No active lynksavvy vendor found; skipping.")
                return

            today = date.today()
            route_keys = list(_ROUTES.keys())
            seeded = 0
            # Seed today + the previous 5 days so the default 7-day window on the
            # Tracking page shows a populated attendance log and a drawable route.
            for d in range(0, 6):
                day = today - timedelta(days=d)
                route = _ROUTES[route_keys[d % len(route_keys)]]
                pts = _build_points(route, day, start_hour=9 + (d % 2))
                dist, start_t, end_t, dur = _stats(pts)
                await conn.execute(text(
                    """
                    INSERT INTO vendor_tracks
                        (tenant_id, vendor_id, track_date, points, point_count,
                         total_distance_meters, start_time, end_time, duration_seconds,
                         status, created_at, updated_at)
                    VALUES
                        (:tenant_id, :vendor_id, :track_date, CAST(:points AS JSONB), :pc,
                         :dist, :start_t, :end_t, :dur, 'completed', now(), now())
                    ON CONFLICT (vendor_id, track_date) DO UPDATE SET
                        points = EXCLUDED.points,
                        point_count = EXCLUDED.point_count,
                        total_distance_meters = EXCLUDED.total_distance_meters,
                        start_time = EXCLUDED.start_time,
                        end_time = EXCLUDED.end_time,
                        duration_seconds = EXCLUDED.duration_seconds,
                        status = EXCLUDED.status,
                        updated_at = now()
                    """
                ), {
                    "tenant_id": tenant_id,
                    "vendor_id": vendor_id,
                    "track_date": day,
                    "points": json.dumps(pts),
                    "pc": len(pts),
                    "dist": dist,
                    "start_t": start_t,
                    "end_t": end_t,
                    "dur": dur,
                })
                seeded += 1
            logger.warning(f"[demo_seed] Seeded {seeded} demo tracks for vendor {vendor_id} "
                           f"(tenant {tenant_id}).")
    except Exception as e:
        # Never let demo seeding affect startup.
        logger.warning(f"[demo_seed] Skipped due to error: {e}")


async def delete_demo_tracks(engine) -> None:
    """Remove demo tracks for the lynksavvy vendor. Run with SEED_DEMO_TRACKS unset by
    calling this manually if cleanup is desired. Safe no-op on failure."""
    try:
        async with engine.begin() as conn:
            vendor_id, _ = await _resolve_vendor(conn)
            if vendor_id:
                await conn.execute(text(
                    "DELETE FROM vendor_tracks WHERE vendor_id = :v"), {"v": vendor_id})
                logger.warning(f"[demo_seed] Deleted demo tracks for vendor {vendor_id}.")
    except Exception as e:
        logger.warning(f"[demo_seed] Cleanup error: {e}")
