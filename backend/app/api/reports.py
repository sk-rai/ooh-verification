"""
Reports API endpoints.
Provides CSV, GeoJSON, PDF, charts, and analytics for campaigns.
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
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
    from app.models.campaign_vendor_assignment import CampaignVendorAssignment

    campaigns_count = await db.execute(
        select(func.count()).select_from(Campaign).where(Campaign.tenant_id == client.tenant_id)
    )
    photos_count = await db.execute(
        select(func.count()).select_from(Photo).where(Photo.tenant_id == client.tenant_id)
    )
    vendors_count = await db.execute(
        select(func.count()).select_from(Vendor).where(Vendor.tenant_id == client.tenant_id)
    )
    verified_count = await db.execute(
        select(func.count()).select_from(Photo).where(
            Photo.tenant_id == client.tenant_id,
            Photo.status == 'verified'
        )
    )
    return {
        "total_campaigns": campaigns_count.scalar() or 0,
        "total_photos": photos_count.scalar() or 0,
        "total_vendors": vendors_count.scalar() or 0,
        "verified_photos": verified_count.scalar() or 0,
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
    result = []
    for c in campaigns.scalars().all():
        photo_count = await db.execute(
            select(func.count()).select_from(Photo).where(Photo.campaign_id == c.campaign_id)
        )
        result.append({
            "campaign_id": str(c.campaign_id),
            "campaign_code": c.campaign_code,
            "name": c.name,
            "status": c.status,
            "campaign_type": c.campaign_type,
            "photo_count": photo_count.scalar() or 0,
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
    result = []
    for v in vendors.scalars().all():
        photo_count = await db.execute(
            select(func.count()).select_from(Photo).where(Photo.vendor_id == v.vendor_id)
        )
        result.append({
            "vendor_id": v.vendor_id,
            "name": v.name,
            "status": v.status,
            "photo_count": photo_count.scalar() or 0,
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
    return [{"date": str(row.date), "count": row.count} for row in result.all()]
