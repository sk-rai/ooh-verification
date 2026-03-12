"""
Tests for Reports API endpoints.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import json

from app.models.campaign import Campaign, CampaignType, CampaignStatus
from app.models.photo import Photo, VerificationStatus
from app.models.sensor_data import SensorData
from app.models.audit_log import AuditLog


@pytest.mark.asyncio
async def test_download_csv_report(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_token: str,
    test_campaign: Campaign,
                                test_vendor
):
    """Test CSV report download."""
    # Create test photos
    for i in range(3):
        photo = Photo(
        tenant_id=test_campaign.tenant_id,
        campaign_id=test_campaign.campaign_id,
        vendor_id=test_vendor.vendor_id,
            capture_timestamp=datetime.utcnow() - timedelta(hours=i),
            verification_status=VerificationStatus.VERIFIED,
            location_match_score=85.5 + i
        )
        db_session.add(photo)
        await db_session.flush()
        
        # Add sensor data
        sensor = SensorData(
            photo_id=photo.photo_id,
            gps_latitude=12.9716 + (i * 0.001),
            gps_longitude=77.5946 + (i * 0.001),
            gps_accuracy=5.0,
            wifi_bssids=["AA:BB:CC:DD:EE:FF"],
            cell_tower_ids=["12345"]
        )
        db_session.add(sensor)
    
    await db_session.commit()
    
    # Download CSV
    response = await async_client.get(
        f"/reports/campaigns/{test_campaign.campaign_code}/csv",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "campaign_" in response.headers["content-disposition"]
    
    # Check CSV content
    csv_content = response.text
    lines = csv_content.strip().split('\n')
    assert len(lines) == 4  # Header + 3 data rows
    assert "Photo ID" in lines[0]
    assert "Verification Status" in lines[0]


@pytest.mark.asyncio
async def test_download_geojson_report(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_token: str,
    test_campaign: Campaign,
                                test_vendor
):
    """Test GeoJSON report download."""
    # Create test photos with locations
    locations = [
        (12.9716, 77.5946),
        (12.9726, 77.5956),
        (12.9736, 77.5966)
    ]
    
    for lat, lng in locations:
        photo = Photo(
        tenant_id=test_campaign.tenant_id,
        campaign_id=test_campaign.campaign_id,
        vendor_id=test_vendor.vendor_id,
            capture_timestamp=datetime.utcnow(),
            verification_status=VerificationStatus.VERIFIED,
            location_match_score=90.0
        )
        db_session.add(photo)
        await db_session.flush()
        
        sensor = SensorData(
            photo_id=photo.photo_id,
            gps_latitude=lat,
            gps_longitude=lng,
            gps_accuracy=5.0
        )
        db_session.add(sensor)
    
    await db_session.commit()
    
    # Download GeoJSON
    response = await async_client.get(
        f"/reports/campaigns/{test_campaign.campaign_code}/geojson",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    
    # Check GeoJSON structure
    geojson_data = response.json()
    assert geojson_data["type"] == "FeatureCollection"
    assert len(geojson_data["features"]) == 3
    
    # Check first feature
    feature = geojson_data["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Point"
    assert len(feature["geometry"]["coordinates"]) == 2
    assert "photo_id" in feature["properties"]
    assert "verification_status" in feature["properties"]


@pytest.mark.asyncio
async def test_get_campaign_statistics(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_token: str,
    test_campaign: Campaign,
                                test_vendor
):
    """Test campaign statistics endpoint."""
    # Create photos with different statuses
    statuses = [
        VerificationStatus.VERIFIED,
        VerificationStatus.VERIFIED,
        VerificationStatus.PENDING,
        VerificationStatus.FLAGGED
    ]
    
    for status in statuses:
        photo = Photo(
        tenant_id=test_campaign.tenant_id,
        campaign_id=test_campaign.campaign_id,
        vendor_id=test_vendor.vendor_id,
            capture_timestamp=datetime.utcnow(),
            verification_status=status,
            location_match_score=85.0
        )
        db_session.add(photo)
        await db_session.flush()
        
        sensor = SensorData(
            photo_id=photo.photo_id,
            gps_latitude=12.9716,
            gps_longitude=77.5946,
            gps_accuracy=5.0
        )
        db_session.add(sensor)
    
    await db_session.commit()
    
    # Get statistics
    response = await async_client.get(
        f"/reports/campaigns/{test_campaign.campaign_code}/statistics",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check structure
    assert "campaign" in data
    assert "statistics" in data
    assert "raw_data" in data
    
    # Check statistics
    stats = data["statistics"]
    assert stats["total_photos"] == 4
    assert stats["status_counts"]["verified"] == 2
    assert stats["status_counts"]["pending"] == 1
    assert stats["status_counts"]["flagged"] == 1
    assert stats["average_confidence"] == 85.0


@pytest.mark.asyncio
async def test_get_campaign_chart_verification(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_token: str,
    test_campaign: Campaign,
                                test_vendor
):
    """Test verification status chart generation."""
    # Create test photos
    photo = Photo(
        tenant_id=test_campaign.tenant_id,
        campaign_id=test_campaign.campaign_id,
        vendor_id=test_vendor.vendor_id,
        capture_timestamp=datetime.utcnow(),
        verification_status=VerificationStatus.VERIFIED,
        location_match_score=90.0
    )
    db_session.add(photo)
    await db_session.flush()
    
    sensor = SensorData(
        photo_id=photo.photo_id,
        gps_latitude=12.9716,
        gps_longitude=77.5946,
        gps_accuracy=5.0
    )
    db_session.add(sensor)
    await db_session.commit()
    
    # Get chart in JSON format
    response = await async_client.get(
        f"/reports/campaigns/{test_campaign.campaign_code}/charts/verification?format=json",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 200
    
    # Parse Plotly JSON
    chart_data = json.loads(response.text)
    assert "data" in chart_data
    assert "layout" in chart_data


@pytest.mark.asyncio
async def test_get_campaign_dashboard(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_token: str,
    test_campaign: Campaign,
                                test_vendor
):
    """Test complete dashboard data endpoint."""
    # Create test photo
    photo = Photo(
        tenant_id=test_campaign.tenant_id,
        campaign_id=test_campaign.campaign_id,
        vendor_id=test_vendor.vendor_id,
        capture_timestamp=datetime.utcnow(),
        verification_status=VerificationStatus.VERIFIED,
        location_match_score=90.0
    )
    db_session.add(photo)
    await db_session.flush()
    
    sensor = SensorData(
        photo_id=photo.photo_id,
        gps_latitude=12.9716,
        gps_longitude=77.5946,
        gps_accuracy=5.0
    )
    db_session.add(sensor)
    await db_session.commit()
    
    # Get dashboard data
    response = await async_client.get(
        f"/reports/campaigns/{test_campaign.campaign_code}/dashboard",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check all components present
    assert "statistics" in data
    assert "charts" in data
    assert "map" in data
    
    # Check charts
    assert "verification" in data["charts"]
    assert "confidence" in data["charts"]
    assert "timeline" in data["charts"]
    
    # Check map
    assert data["map"]["type"] == "FeatureCollection"


@pytest.mark.asyncio
async def test_invalid_chart_type(
    async_client: AsyncClient,
    client_token: str,
    test_campaign: Campaign,
                                test_vendor
):
    """Test invalid chart type returns 400."""
    response = await async_client.get(
        f"/reports/campaigns/{test_campaign.campaign_code}/charts/invalid_type",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 400
    assert "Invalid chart type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_campaign_not_found(
    async_client: AsyncClient,
    client_token: str
):
    """Test 404 for non-existent campaign."""
    response = await async_client.get(
        "/reports/campaigns/NONEXISTENT/statistics",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 404
