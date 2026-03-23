"""
Reports API endpoints.
Provides CSV, GeoJSON, PDF, charts, and analytics for campaigns.
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import io

from app.core.database import get_db
from app.core.deps import get_current_client
from app.models.client import Client
from app.services.report_generator import ReportGenerator
from app.services.chart_generator import ChartGenerator
from app.services.map_generator import MapGenerator

router = APIRouter(prefix="/api/reports", tags=["reports"])


def get_report_generator(db: AsyncSession = Depends(get_db)) -> ReportGenerator:
    """Dependency for report generator."""
    chart_gen = ChartGenerator()
    map_gen = MapGenerator()
    return ReportGenerator(db, chart_gen, map_gen)


@router.get("/campaigns/{campaign_code}/csv")
async def download_csv_report(
    campaign_code: str,
    current_client: Client = Depends(get_current_client),
    report_gen: ReportGenerator = Depends(get_report_generator)
):
    """
    Download CSV report for a campaign.
    
    Returns CSV file with all photo data including:
    - Photo metadata
    - GPS coordinates with 7 decimal precision
    - Sensor data summary
    - Verification status
    - Audit flags
    
    Requirements: 3.1, 3.2, 3.3, 3.4, 7.1
    """
    try:
        csv_content = await report_gen.generate_csv_report(campaign_code)
        
        return StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=campaign_{campaign_code}_report.csv"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating CSV report: {str(e)}")


@router.get("/campaigns/{campaign_code}/geojson")
async def download_geojson_report(
    campaign_code: str,
    current_client: Client = Depends(get_current_client),
    report_gen: ReportGenerator = Depends(get_report_generator)
):
    """
    Download GeoJSON report for a campaign.
    
    Returns GeoJSON FeatureCollection with all photo locations.
    Can be used with mapping libraries like Mapbox, Leaflet, etc.
    
    Requirements: 3.1, 3.2, 3.3, 3.4
    """
    try:
        geojson_data = await report_gen.generate_geojson_report(campaign_code)
        
        return JSONResponse(
            content=geojson_data,
            headers={
                "Content-Disposition": f"attachment; filename=campaign_{campaign_code}_map.geojson"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating GeoJSON report: {str(e)}")


@router.get("/campaigns/{campaign_code}/pdf")
async def download_pdf_report(
    campaign_code: str,
    current_client: Client = Depends(get_current_client),
    report_gen: ReportGenerator = Depends(get_report_generator)
):
    """
    Download PDF report for a campaign.
    
    Returns comprehensive PDF report with:
    - Campaign summary
    - Statistics and metrics
    - Verification status charts
    - Photo timeline
    - Vendor performance
    
    Requirements: 3.1, 3.2, 3.3, 3.4
    """
    try:
        from app.services.pdf_generator import PDFGenerator
        
        # Get campaign statistics
        stats = await report_gen.get_campaign_statistics(campaign_code)
        campaign_data = stats['campaign']
        
        # Generate charts as PNG images
        chart_images = {}
        for chart_type in ['verification', 'confidence', 'timeline']:
            try:
                chart_images[chart_type] = await report_gen.generate_chart_data(
                    campaign_code, chart_type, 'png'
                )
            except Exception as e:
                print(f"Warning: Could not generate {chart_type} chart: {e}")
                chart_images[chart_type] = None
        
        # Generate PDF
        pdf_gen = PDFGenerator()
        pdf_bytes = pdf_gen.generate_campaign_report(
            campaign_data=campaign_data,
            statistics=stats,
            chart_images=chart_images
        )
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=campaign_{campaign_code}_report.pdf"
            }
        )
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="PDF generation not available. ReportLab library is not installed."
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF report: {str(e)}")


@router.get("/campaigns/{campaign_code}/statistics")
async def get_campaign_statistics(
    campaign_code: str,
    current_client: Client = Depends(get_current_client),
    report_gen: ReportGenerator = Depends(get_report_generator)
):
    """
    Get campaign statistics and analytics.
    
    Returns:
    - Total photo count
    - Verification status breakdown
    - Average confidence score
    - Flagged photos count
    - Vendor performance
    - Audit flag distribution
    """
    try:
        stats = await report_gen.get_campaign_statistics(campaign_code)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating statistics: {str(e)}")


@router.get("/campaigns/{campaign_code}/charts/{chart_type}")
async def get_campaign_chart(
    campaign_code: str,
    chart_type: str,
    format: str = "json",
    current_client: Client = Depends(get_current_client),
    report_gen: ReportGenerator = Depends(get_report_generator)
):
    """
    Get chart data for a campaign.
    
    Chart types:
    - verification: Pie chart of verification status distribution
    - confidence: Histogram of confidence scores
    - timeline: Line chart of photos over time
    
    Formats:
    - json: Plotly JSON (for web UI)
    - html: Standalone HTML with embedded chart
    - png: PNG image (for PDF reports)
    """
    valid_types = ['verification', 'confidence', 'timeline']
    valid_formats = ['json', 'html', 'png']
    
    if chart_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid chart type. Must be one of: {', '.join(valid_types)}"
        )
    
    if format not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format. Must be one of: {', '.join(valid_formats)}"
        )
    
    try:
        chart_data = await report_gen.generate_chart_data(campaign_code, chart_type, format)
        
        if format == 'json':
            return Response(content=chart_data, media_type="application/json")
        elif format == 'html':
            return Response(content=chart_data, media_type="text/html")
        elif format == 'png':
            return Response(content=chart_data, media_type="image/png")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating chart: {str(e)}")


@router.get("/campaigns/{campaign_code}/dashboard")
async def get_campaign_dashboard(
    campaign_code: str,
    current_client: Client = Depends(get_current_client),
    report_gen: ReportGenerator = Depends(get_report_generator)
):
    """
    Get complete dashboard data for a campaign.
    
    Returns:
    - Campaign statistics
    - All charts in JSON format
    - GeoJSON map data
    
    This endpoint provides all data needed for a web dashboard in one call.
    """
    try:
        stats = await report_gen.get_campaign_statistics(campaign_code)
        geojson_data = await report_gen.generate_geojson_report(campaign_code)
        
        # Generate all charts
        charts = {}
        for chart_type in ['verification', 'confidence', 'timeline']:
            try:
                charts[chart_type] = await report_gen.generate_chart_data(
                    campaign_code, chart_type, 'json'
                )
            except:
                charts[chart_type] = None
        
        return {
            'statistics': stats,
            'charts': charts,
            'map': geojson_data
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating dashboard: {str(e)}")


@router.get("/statistics")
async def get_aggregate_statistics(
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client)
):
    """Get aggregate statistics across all campaigns."""
    from sqlalchemy import func
    from app.models import Campaign, Photo, Vendor
    from app.models.photo import VerificationStatus
    from app.models.campaign import CampaignStatus
    from app.models.vendor import VendorStatus

    total_photos = (await db.execute(
        select(func.count()).select_from(Photo).where(Photo.tenant_id == client.tenant_id)
    )).scalar() or 0
    verified = (await db.execute(
        select(func.count()).select_from(Photo).where(
            Photo.tenant_id == client.tenant_id, Photo.verification_status == VerificationStatus.VERIFIED
        )
    )).scalar() or 0
    rejected = (await db.execute(
        select(func.count()).select_from(Photo).where(
            Photo.tenant_id == client.tenant_id, Photo.verification_status == VerificationStatus.REJECTED
        )
    )).scalar() or 0
    pending = total_photos - verified - rejected

    total_campaigns = (await db.execute(
        select(func.count()).select_from(Campaign).where(Campaign.tenant_id == client.tenant_id)
    )).scalar() or 0
    active_campaigns = (await db.execute(
        select(func.count()).select_from(Campaign).where(
            Campaign.tenant_id == client.tenant_id, Campaign.status == CampaignStatus.ACTIVE
        )
    )).scalar() or 0

    total_vendors = (await db.execute(
        select(func.count()).select_from(Vendor).where(Vendor.tenant_id == client.tenant_id)
    )).scalar() or 0
    active_vendors = (await db.execute(
        select(func.count()).select_from(Vendor).where(
            Vendor.tenant_id == client.tenant_id, Vendor.status == VendorStatus.ACTIVE
        )
    )).scalar() or 0

    return {
        "total_photos": total_photos,
        "verified_photos": verified,
        "failed_photos": rejected,
        "pending_photos": pending,
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "total_vendors": total_vendors,
        "active_vendors": active_vendors,
    }

@router.get("/campaigns")
async def get_campaigns_report(
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client)
):
    """Get campaign-level report data."""
    from sqlalchemy import func
    from app.models import Campaign, Photo

    campaigns = await db.execute(
        select(Campaign).where(Campaign.tenant_id == client.tenant_id).order_by(Campaign.created_at.desc())
    )
    from app.models.photo import VerificationStatus
    result = []
    for c in campaigns.scalars().all():
        photo_count = (await db.execute(
            select(func.count()).select_from(Photo).where(Photo.campaign_id == c.campaign_id)
        )).scalar() or 0
        verified_count = (await db.execute(
            select(func.count()).select_from(Photo).where(
                Photo.campaign_id == c.campaign_id,
                Photo.verification_status == VerificationStatus.VERIFIED
            )
        )).scalar() or 0
        result.append({
            "campaign_id": str(c.campaign_id),
            "campaign_code": c.campaign_code,
            "campaign_name": c.name,
            "name": c.name,
            "status": c.status.value if hasattr(c.status, 'value') else str(c.status),
            "campaign_type": c.campaign_type,
            "photo_count": photo_count,
            "verified_count": verified_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return result

@router.get("/vendors")
async def get_vendors_report(
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client)
):
    """Get vendor-level report data."""
    from sqlalchemy import func
    from app.models import Vendor, Photo

    vendors = await db.execute(
        select(Vendor).where(Vendor.tenant_id == client.tenant_id)
    )
    from app.models.photo import VerificationStatus
    result = []
    for v in vendors.scalars().all():
        photo_count = (await db.execute(
            select(func.count()).select_from(Photo).where(Photo.vendor_id == v.vendor_id)
        )).scalar() or 0
        verified_count = (await db.execute(
            select(func.count()).select_from(Photo).where(
                Photo.vendor_id == v.vendor_id,
                Photo.verification_status == VerificationStatus.VERIFIED
            )
        )).scalar() or 0
        result.append({
            "vendor_id": v.vendor_id,
            "vendor_name": v.name,
            "name": v.name,
            "status": v.status.value if hasattr(v.status, 'value') else str(v.status),
            "photo_count": photo_count,
            "verified_count": verified_count,
            "verification_rate": (verified_count / photo_count) if photo_count > 0 else 0,
        })
    return result

@router.get("/time-series")
async def get_time_series(
    start: str = None,
    end: str = None,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client)
):
    """Get photo upload time series data."""
    from sqlalchemy import func, cast, Date
    from app.models import Photo
    from datetime import datetime, timedelta

    query = select(
        cast(Photo.created_at, Date).label("date"),
        func.count().label("count")
    ).where(Photo.tenant_id == client.tenant_id)

    if start:
        query = query.where(Photo.created_at >= datetime.fromisoformat(start))
    if end:
        query = query.where(Photo.created_at <= datetime.fromisoformat(end))

    query = query.group_by(cast(Photo.created_at, Date)).order_by(cast(Photo.created_at, Date))
    result = await db.execute(query)
    return [{"date": str(row.date), "photo_count": row.count, "count": row.count} for row in result.all()]


@router.get("/export/csv")
async def export_csv(
    start_date: str = None,
    end_date: str = None,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client)
):
    """Export all photos as CSV."""
    from sqlalchemy import func, cast, Date
    from app.models import Photo, Campaign, Vendor, SensorData
    from datetime import datetime

    query = (
        select(Photo, Campaign.name.label("campaign_name"), Campaign.campaign_code,
               Vendor.name.label("vendor_name"), Vendor.vendor_id.label("vid"),
               SensorData.gps_latitude, SensorData.gps_longitude, SensorData.gps_accuracy)
        .join(Campaign, Campaign.campaign_id == Photo.campaign_id, isouter=True)
        .join(Vendor, Vendor.vendor_id == Photo.vendor_id, isouter=True)
        .join(SensorData, SensorData.photo_id == Photo.photo_id, isouter=True)
        .where(Photo.tenant_id == client.tenant_id)
    )
    if start_date:
        query = query.where(Photo.created_at >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(Photo.created_at <= datetime.fromisoformat(end_date))
    query = query.order_by(Photo.created_at.desc())

    result = await db.execute(query)
    rows = result.all()

    csv_lines = ["photo_id,campaign_code,campaign_name,vendor_id,vendor_name,status,confidence,latitude,longitude,accuracy,captured_at,rejection_reasons"]
    for row in rows:
        p = row[0]
        csv_lines.append(",".join([
            str(p.photo_id),
            str(row.campaign_code or ""),
            str(row.campaign_name or "").replace(",", ";"),
            str(row.vid or ""),
            str(row.vendor_name or "").replace(",", ";"),
            p.verification_status.value if hasattr(p.verification_status, 'value') else str(p.verification_status),
            str(p.verification_confidence or 0),
            str(row.gps_latitude or 0),
            str(row.gps_longitude or 0),
            str(row.gps_accuracy or 0),
            p.created_at.isoformat() if p.created_at else "",
        ]))

    csv_content = "\n".join(csv_lines)
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=trustcapture-report.csv"}
    )


@router.get("/export/pdf")
async def export_pdf(
    start_date: str = None,
    end_date: str = None,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client)
):
    """Export summary as PDF (simple text-based)."""
    from sqlalchemy import func
    from app.models import Photo, Campaign, Vendor
    from app.models.photo import VerificationStatus

    total = (await db.execute(select(func.count()).select_from(Photo).where(Photo.tenant_id == client.tenant_id))).scalar() or 0
    verified = (await db.execute(select(func.count()).select_from(Photo).where(Photo.tenant_id == client.tenant_id, Photo.verification_status == VerificationStatus.VERIFIED))).scalar() or 0
    rejected = (await db.execute(select(func.count()).select_from(Photo).where(Photo.tenant_id == client.tenant_id, Photo.verification_status == VerificationStatus.REJECTED))).scalar() or 0
    campaigns = (await db.execute(select(func.count()).select_from(Campaign).where(Campaign.tenant_id == client.tenant_id))).scalar() or 0
    vendors = (await db.execute(select(func.count()).select_from(Vendor).where(Vendor.tenant_id == client.tenant_id))).scalar() or 0

    content = f"""TrustCapture Report
====================
Total Photos: {total}
Verified: {verified}
Rejected: {rejected}
Pending: {total - verified - rejected}
Campaigns: {campaigns}
Vendors: {vendors}
"""
    return Response(
        content=content.encode(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=trustcapture-report.pdf"}
    )
