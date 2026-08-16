"""
Site Visit Report API — attendance/field presence reports for campaigns.

Provides per-vendor per-day summaries with distance calculation,
filtered by date range and campaign. Excludes Quick Capture (no campaign).
"""
import math
import csv
import io
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from uuid import UUID

from app.core.database import get_db
from app.core.deps import get_current_client
from app.models.client import Client
from app.models.campaign import Campaign, CampaignStatus
from app.models.vendor import Vendor
from app.models.evidence import Evidence

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports/site-visits", tags=["site-visits"])


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two GPS coordinates."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_route_distance(points: List[Dict[str, float]]) -> float:
    """Calculate total route distance from ordered GPS points. Returns meters."""
    total = 0.0
    for i in range(1, len(points)):
        prev = points[i - 1]
        curr = points[i]
        if prev["lat"] and prev["lon"] and curr["lat"] and curr["lon"]:
            total += haversine_distance(prev["lat"], prev["lon"], curr["lat"], curr["lon"])
    return total


@router.get("")
async def get_site_visits(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    campaign_id: Optional[str] = Query(None, description="Filter by specific campaign"),
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    """
    Get site visit report — per vendor per campaign per day.

    Only includes campaign-assigned evidence (excludes Quick Capture).
    Only includes campaigns that were active during the report period.
    """
    # Parse dates
    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Get eligible campaigns (active or ended during/after report start)
    campaign_query = select(Campaign).where(
        Campaign.client_id == client.client_id,
        Campaign.start_date <= end_dt,  # Campaign started before report ends
    )
    if campaign_id:
        campaign_query = campaign_query.where(Campaign.campaign_id == campaign_id)

    campaign_result = await db.execute(campaign_query)
    campaigns = {str(c.campaign_id): c for c in campaign_result.scalars().all()}

    if not campaigns:
        return {"report_period": {"start": start_date, "end": end_date}, "rows": [], "summary": {
            "total_vendors_active": 0, "total_captures": 0, "total_distance_km": 0, "avg_hours_per_vendor": 0
        }}

    # Query evidence from BOTH tables for these campaigns in date range
    # 1. From evidence table
    evidence_query = select(Evidence).where(
        Evidence.tenant_id == client.tenant_id,
        Evidence.campaign_id.in_([UUID(cid) for cid in campaigns.keys()]),
        Evidence.created_at >= start_dt,
        Evidence.created_at < end_dt,
    ).order_by(Evidence.created_at)

    evidence_result = await db.execute(evidence_query)
    evidence_items = evidence_result.scalars().all()

    # 2. From photos table (legacy)
    from app.models import Photo, SensorData
    photo_query = (
        select(Photo, SensorData.gps_latitude, SensorData.gps_longitude)
        .join(SensorData, SensorData.photo_id == Photo.photo_id, isouter=True)
        .where(
            Photo.tenant_id == client.tenant_id,
            Photo.campaign_id.in_([UUID(cid) for cid in campaigns.keys()]),
            Photo.created_at >= start_dt,
            Photo.created_at < end_dt,
        )
        .order_by(Photo.created_at)
    )
    photo_result = await db.execute(photo_query)
    photo_rows = photo_result.all()

    # Get vendors info
    vendor_ids = set()
    for e in evidence_items:
        vendor_ids.add(e.vendor_id)
    for row in photo_rows:
        if row[0].vendor_id:
            vendor_ids.add(row[0].vendor_id)

    vendor_result = await db.execute(select(Vendor).where(Vendor.vendor_id.in_(list(vendor_ids))))
    vendors = {v.vendor_id: v for v in vendor_result.scalars().all()}

    # Group by (campaign_id, vendor_id, date)
    # Key: (campaign_id_str, vendor_id, date_str) -> list of captures
    groups: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)

    for e in evidence_items:
        capture_date = e.created_at.strftime("%Y-%m-%d") if e.created_at else None
        if not capture_date:
            continue
        key = (str(e.campaign_id), e.vendor_id, capture_date)
        groups[key].append({
            "lat": e.latitude or 0,
            "lon": e.longitude or 0,
            "time": e.created_at,
            "type": e.evidence_type,
            "status": e.verification_status,
        })

    for row in photo_rows:
        photo = row[0]
        capture_date = photo.created_at.strftime("%Y-%m-%d") if photo.created_at else None
        if not capture_date or not photo.campaign_id:
            continue
        key = (str(photo.campaign_id), photo.vendor_id, capture_date)
        groups[key].append({
            "lat": float(row.gps_latitude) if row.gps_latitude else 0,
            "lon": float(row.gps_longitude) if row.gps_longitude else 0,
            "time": photo.created_at,
            "type": "photo",
            "status": photo.verification_status.value if hasattr(photo.verification_status, 'value') else str(photo.verification_status),
        })

    # Build report rows
    rows = []
    total_distance = 0.0
    active_vendors = set()

    for (campaign_id_str, vendor_id, capture_date), captures in sorted(groups.items(), key=lambda x: x[0][2], reverse=True):
        campaign = campaigns.get(campaign_id_str)
        vendor = vendors.get(vendor_id)
        if not campaign or not vendor:
            continue

        active_vendors.add(vendor_id)

        # Sort captures by time
        captures.sort(key=lambda c: c["time"] if c["time"] else datetime.min)

        # Count by type
        photos_count = sum(1 for c in captures if c["type"] == "photo")
        videos_count = sum(1 for c in captures if c["type"] == "video")
        voice_count = sum(1 for c in captures if c["type"] == "voice_note")
        text_count = sum(1 for c in captures if c["type"] == "text_note")

        # Count by status
        verified_count = sum(1 for c in captures if c["status"] == "verified")
        flagged_count = sum(1 for c in captures if c["status"] == "flagged")
        rejected_count = sum(1 for c in captures if c["status"] == "rejected")

        # Time range
        times = [c["time"] for c in captures if c["time"]]
        first_capture = min(times).strftime("%H:%M:%S") if times else None
        last_capture = max(times).strftime("%H:%M:%S") if times else None
        hours_active = 0.0
        if len(times) >= 2:
            hours_active = (max(times) - min(times)).total_seconds() / 3600.0

        # Distance calculation
        valid_points = [{"lat": c["lat"], "lon": c["lon"]} for c in captures if c["lat"] and c["lon"] and c["lat"] != 0 and c["lon"] != 0]
        distance_m = calculate_route_distance(valid_points) if len(valid_points) >= 2 else 0.0
        distance_km = round(distance_m / 1000.0, 2)
        total_distance += distance_km

        rows.append({
            "date": capture_date,
            "campaign_name": campaign.name,
            "campaign_code": campaign.campaign_code,
            "vendor_name": vendor.name,
            "vendor_id": vendor.vendor_id,
            "vendor_phone": vendor.phone_number,
            "total_captures": len(captures),
            "photos": photos_count,
            "videos": videos_count,
            "voice_notes": voice_count,
            "text_notes": text_count,
            "first_capture": first_capture,
            "last_capture": last_capture,
            "hours_active": round(hours_active, 2),
            "distance_km": distance_km,
            "verified": verified_count,
            "flagged": flagged_count,
            "rejected": rejected_count,
        })

    # Summary
    summary = {
        "total_vendors_active": len(active_vendors),
        "total_captures": sum(r["total_captures"] for r in rows),
        "total_distance_km": round(total_distance, 2),
        "avg_hours_per_vendor": round(
            sum(r["hours_active"] for r in rows) / len(active_vendors), 2
        ) if active_vendors else 0,
    }

    return {"report_period": {"start": start_date, "end": end_date}, "rows": rows, "summary": summary}


@router.get("/export/csv")
async def export_site_visits_csv(
    start_date: str = Query(...),
    end_date: str = Query(...),
    campaign_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    """Export site visit report as CSV."""
    # Reuse the main endpoint logic
    from starlette.datastructures import QueryParams
    from fastapi import Request

    # Call the main function directly (internal reuse)
    report = await get_site_visits(
        start_date=start_date, end_date=end_date, campaign_id=campaign_id, db=db, client=client
    )

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Date", "Campaign", "Campaign Code", "Vendor Name", "Vendor ID", "Vendor Phone",
        "Total Captures", "Photos", "Videos", "Voice Notes",
        "First Capture", "Last Capture", "Hours Active", "Distance (km)",
        "Verified", "Flagged", "Rejected"
    ])

    # Data rows
    for row in report["rows"]:
        writer.writerow([
            row["date"], row["campaign_name"], row["campaign_code"],
            row["vendor_name"], row["vendor_id"], row["vendor_phone"],
            row["total_captures"], row["photos"], row["videos"], row["voice_notes"],
            row["first_capture"], row["last_capture"], row["hours_active"], row["distance_km"],
            row["verified"], row["flagged"], row["rejected"],
        ])

    # Summary row
    writer.writerow([])
    writer.writerow(["SUMMARY"])
    writer.writerow(["Total Active Vendors", report["summary"]["total_vendors_active"]])
    writer.writerow(["Total Captures", report["summary"]["total_captures"]])
    writer.writerow(["Total Distance (km)", report["summary"]["total_distance_km"]])
    writer.writerow(["Avg Hours/Vendor", report["summary"]["avg_hours_per_vendor"]])

    csv_content = output.getvalue()
    filename = f"site_visits_{start_date}_to_{end_date}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/pdf")
async def export_site_visits_pdf(
    start_date: str = Query(...),
    end_date: str = Query(...),
    campaign_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    """Export site visit report as PDF."""
    from fpdf import FPDF

    report = await get_site_visits(
        start_date=start_date, end_date=end_date, campaign_id=campaign_id, db=db, client=client
    )

    pdf = FPDF()
    pdf.add_page("L")  # Landscape for wide table
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "TrustCapture - Site Visit Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Period: {start_date} to {end_date}", ln=True, align="C")
    pdf.ln(5)

    # Summary
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, f"Active Vendors: {report['summary']['total_vendors_active']}  |  "
                   f"Total Captures: {report['summary']['total_captures']}  |  "
                   f"Total Distance: {report['summary']['total_distance_km']} km  |  "
                   f"Avg Hours/Vendor: {report['summary']['avg_hours_per_vendor']}", ln=True)
    pdf.ln(5)

    # Table header
    pdf.set_font("Helvetica", "B", 7)
    col_widths = [18, 35, 28, 18, 18, 12, 12, 12, 15, 15, 12, 15, 12, 12, 12]
    headers = ["Date", "Campaign", "Vendor", "ID", "Phone", "Caps", "Pics", "Vids",
               "First", "Last", "Hours", "Dist(km)", "OK", "Flag", "Rej"]
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 6, h, border=1)
    pdf.ln()

    # Table rows
    pdf.set_font("Helvetica", "", 7)
    for row in report["rows"][:100]:  # Limit to 100 rows for PDF
        cells = [
            row["date"][-5:], row["campaign_name"][:20], row["vendor_name"][:16],
            row["vendor_id"], row["vendor_phone"][-10:] if row["vendor_phone"] else "",
            str(row["total_captures"]), str(row["photos"]), str(row["videos"]),
            row["first_capture"][:5] if row["first_capture"] else "-",
            row["last_capture"][:5] if row["last_capture"] else "-",
            str(row["hours_active"]), str(row["distance_km"]),
            str(row["verified"]), str(row["flagged"]), str(row["rejected"]),
        ]
        for i, cell in enumerate(cells):
            pdf.cell(col_widths[i], 5, cell, border=1)
        pdf.ln()

    pdf_bytes = pdf.output()
    filename = f"site_visits_{start_date}_to_{end_date}.pdf"

    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
