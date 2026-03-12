"""Tests for reports API endpoints."""
import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta
import json

from app.models.campaign import Campaign, CampaignType, CampaignStatus
from app.models.photo import Photo, VerificationStatus
from app.models.sensor_data import SensorData

@pytest.mark.asyncio
async def test_download_csv_report(async_client: AsyncClient,
                                    client_token: str,
                                    test_campaign: Campaign,
                                    test_vendor,
                                    db_session):
    """Test CSV report download."""
    # Create test photos
    photo = Photo(
        tenant_id=test_campaign.tenant_id,
        campaign_id=test_campaign.campaign_id,
        vendor_id=test_vendor.vendor_id,
        verification_status=VerificationStatus.VERIFIED,
        location_match_score=95.5,
        s3_key="test/photo.jpg",
        capture_timestamp=datetime.utcnow()
    )
    db_session.add(photo)
    await db_session.commit()
    await db_session.refresh(photo)
    
    # Add sensor data
    sensor = SensorData(
        photo_id=photo.photo_id,
        gps_latitude=37.7749,
        gps_longitude=-122.4194,
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
    
    # Verify CSV content
    csv_content = response.text
    assert "Photo ID" in csv_content
    assert str(photo.photo_id) in csv_content
    assert "VERIFIED" in csv_content

@pytest.mark.asyncio
async def test_download_geojson_report(async_client: AsyncClient,
                                        client_token: str,
                                        test_campaign: Campaign,
                                        test_vendor,
                                        db_session):
    """Test GeoJSON report download."""
    # Create test photo with location
    photo = Photo(
        tenant_id=test_campaign.tenant_id,
        campaign_id=test_campaign.campaign_id,
        vendor_id=test_vendor.vendor_id,
        verification_status=VerificationStatus.VERIFIED,
        location_match_score=95.5,
        s3_key="test/photo.jpg",
        capture_timestamp=datetime.utcnow()
    )
    db_session.add(photo)
    await db_session.commit()
    await db_session.refresh(photo)
    
    sensor = SensorData(
        photo_id=photo.photo_id,
        gps_latitude=37.7749,
        gps_longitude=-122.4194,
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
    
    # Verify GeoJSON structure
    geojson = response.json()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 1
    assert geojson["features"][0]["geometry"]["type"] == "Point"
    assert geojson["features"][0]["geometry"]["coordinates"] == [-122.4194, 37.7749]

@pytest.mark.asyncio
async def test_get_campaign_statistics(async_client: AsyncClient,
                                        client_token: str,
                                        test_campaign: Campaign,
                                        test_vendor,
                                        db_session):
    """Test campaign statistics endpoint."""
    # Create multiple photos with different statuses
    statuses = [
        VerificationStatus.VERIFIED,
        VerificationStatus.VERIFIED,
        VerificationStatus.PENDING,
        VerificationStatus.FLAGGED
    ]
    
    for i, status in enumerate(statuses):
        photo = Photo(
            tenant_id=test_campaign.tenant_id,
            campaign_id=test_campaign.campaign_id,
            s3_key=f"test/photo_{i}.jpg",
            vendor_id=test_vendor.vendor_id,
            verification_status=status,
            location_match_score=90.0 + i,
            capture_timestamp=datetime.utcnow() - timedelta(days=i)
        )
        db_session.add(photo)
    
    await db_session.commit()
    
    # Get statistics
    response = await async_client.get(
        f"/reports/campaigns/{test_campaign.campaign_code}/statistics",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 200
    stats = response.json()
    
    # Verify structure
    assert "campaign" in stats
    assert "statistics" in stats
    assert stats["statistics"]["total_photos"] == 4
    assert stats["statistics"]["status_counts"]["verified"] == 2
    assert stats["statistics"]["status_counts"]["pending"] == 1
    assert stats["statistics"]["status_counts"]["flagged"] == 1
    assert "average_confidence" in stats["statistics"]

@pytest.mark.asyncio
async def test_get_verification_chart(async_client: AsyncClient,
                                       client_token: str,
                                       test_campaign: Campaign,
                                       test_vendor,
                                       db_session):
    """Test verification status chart generation."""
    # Create test photos
    photo = Photo(
        tenant_id=test_campaign.tenant_id,
        campaign_id=test_campaign.campaign_id,
        vendor_id=test_vendor.vendor_id,
        verification_status=VerificationStatus.VERIFIED,
        location_match_score=95.5,
        s3_key="test/photo.jpg",
        capture_timestamp=datetime.utcnow()
    )
    db_session.add(photo)
    await db_session.commit()
    
    # Get chart in JSON format
    response = await async_client.get(
        f"/reports/campaigns/{test_campaign.campaign_code}/charts/verification?format=json",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    
    # Verify it's valid Plotly JSON
    chart_data = json.loads(response.text)
    assert "data" in chart_data
    assert "layout" in chart_data

@pytest.mark.asyncio
async def test_get_confidence_chart(async_client: AsyncClient,
                                     client_token: str,
                                     test_campaign: Campaign,
                                     test_vendor,
                                     db_session):
    """Test confidence score histogram generation."""
    # Create photos with various confidence scores
    for i in range(10):
        photo = Photo(
            tenant_id=test_campaign.tenant_id,
            campaign_id=test_campaign.campaign_id,
            s3_key=f"test/photo_{i}.jpg",
            vendor_id=test_vendor.vendor_id,
            verification_status=VerificationStatus.VERIFIED,
            location_match_score=80.0 + i * 2,
            capture_timestamp=datetime.utcnow()
        )
        db_session.add(photo)
    
    await db_session.commit()
    
    # Get chart
    response = await async_client.get(
        f"/reports/campaigns/{test_campaign.campaign_code}/charts/confidence?format=json",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 200
    chart_data = json.loads(response.text)
    assert "data" in chart_data

@pytest.mark.asyncio
async def test_get_timeline_chart(async_client: AsyncClient,
                                   client_token: str,
                                   test_campaign: Campaign,
                                   test_vendor,
                                   db_session):
    """Test timeline chart generation."""
    # Create photos over multiple days
    for i in range(5):
        photo = Photo(
            tenant_id=test_campaign.tenant_id,
            campaign_id=test_campaign.campaign_id,
            s3_key=f"test/photo_{i}.jpg",
            vendor_id=test_vendor.vendor_id,
            verification_status=VerificationStatus.VERIFIED,
            location_match_score=90.0,
            capture_timestamp=datetime.utcnow() - timedelta(days=i)
        )
        db_session.add(photo)
    
    await db_session.commit()
    
    # Get chart
    response = await async_client.get(
        f"/reports/campaigns/{test_campaign.campaign_code}/charts/timeline?format=json",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 200
    chart_data = json.loads(response.text)
    assert "data" in chart_data

@pytest.mark.asyncio
async def test_get_dashboard(async_client: AsyncClient,
                              client_token: str,
                              test_campaign: Campaign,
                              test_vendor,
                              db_session):
    """Test complete dashboard endpoint."""
    # Create test data
    photo = Photo(
        tenant_id=test_campaign.tenant_id,
        campaign_id=test_campaign.campaign_id,
        vendor_id=test_vendor.vendor_id,
        verification_status=VerificationStatus.VERIFIED,
        location_match_score=95.5,
        s3_key="test/photo.jpg",
        capture_timestamp=datetime.utcnow()
    )
    db_session.add(photo)
    await db_session.commit()
    await db_session.refresh(photo)
    
    sensor = SensorData(
        photo_id=photo.photo_id,
        gps_latitude=37.7749,
        gps_longitude=-122.4194,
        gps_accuracy=5.0
    )
    db_session.add(sensor)
    await db_session.commit()
    
    # Get dashboard
    response = await async_client.get(
        f"/reports/campaigns/{test_campaign.campaign_code}/dashboard",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 200
    dashboard = response.json()
    
    # Verify all components present
    assert "statistics" in dashboard
    assert "charts" in dashboard
    assert "map" in dashboard
    
    # Verify charts
    assert "verification" in dashboard["charts"]
    assert "confidence" in dashboard["charts"]
    assert "timeline" in dashboard["charts"]
    
    # Verify map
    assert dashboard["map"]["type"] == "FeatureCollection"

@pytest.mark.asyncio
async def test_invalid_chart_type(async_client: AsyncClient,
                                   client_token: str,
                                   test_campaign: Campaign):
    """Test error handling for invalid chart type."""
    response = await async_client.get(
        f"/reports/campaigns/{test_campaign.campaign_code}/charts/invalid_type",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 400
    assert "Invalid chart type" in response.json()["detail"]

@pytest.mark.asyncio
async def test_invalid_format(async_client: AsyncClient,
                               client_token: str,
                               test_campaign: Campaign):
    """Test error handling for invalid format."""
    response = await async_client.get(
        f"/reports/campaigns/{test_campaign.campaign_code}/charts/verification?format=invalid",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 400
    assert "Invalid format" in response.json()["detail"]

@pytest.mark.asyncio
async def test_campaign_not_found(async_client: AsyncClient,
                                   client_token: str):
    """Test error handling for non-existent campaign."""
    response = await async_client.get(
        "/reports/campaigns/NONEXISTENT/statistics",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 404

