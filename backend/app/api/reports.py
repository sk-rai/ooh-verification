"""
Reports API endpoints.
Provides CSV, GeoJSON, charts, and analytics for campaigns.
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

router = APIRouter(prefix="/reports", tags=["reports"])


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
    - GPS coordinates
    - Sensor data summary
    - Verification status
    - Audit flags
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
