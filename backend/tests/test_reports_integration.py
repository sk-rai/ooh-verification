"""
Integration tests for report generation API.
Tests CSV, GeoJSON, and PDF export functionality.

Requirements: 3.1, 3.2, 3.3, 3.4, 7.1
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import json
import csv
import io

from app.models.client import Client
from app.models.campaign import Campaign, CampaignType, CampaignStatus
from app.models.vendor import Vendor
from app.models.photo import Photo, VerificationStatus
from app.models.sensor_data import SensorData
from app.models.audit_log import AuditLog


@pytest.fixture
async def test_campaign_with_photos(db_session: AsyncSession, test_client_user: Client):
    """Create a test campaign with sample photos for report testing."""
    # Create campaign
    campaign = Campaign(
        campaign_code="TEST_REPORT_001",
        name="Test Report Campaign",
        campaign_type=CampaignType.OOH_ADVERTISING,
        client_id=test_client_user.client_id,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        status=CampaignStatus.ACTIVE
    )
    db_session.add(campaign)
    await db_session.flush()
    
    # Create vendor
    vendor = Vendor(
        vendor_id="VND001",
        created_by_client_id=test_client_user.client_id,
        name="Test Vendor",
        phone_number="+1234567890"
    )
    db_session.add(vendor)
    await db_session.flush()
    
    # Create sample photos with sensor data
    photos_data = [
        {
            'lat': 28.6139391,
            'lon': 77.2090212,
            'status': VerificationStatus.VERIFIED,
            'score': 95.5
        },
        {
            'lat': 28.6129391,
            'lon': 77.2080212,
            'status': VerificationStatus.VERIFIED,
            'score': 88.3
        },
        {
            'lat': 28.6149391,
            'lon': 77.2100212,
            'status': VerificationStatus.FLAGGED,
            'score': 65.2
        },
        {
            'lat': 28.6159391,
            'lon': 77.2110212,
            'status': VerificationStatus.PENDING,
            'score': None
        }
    ]
    
    for i, photo_data in enumerate(photos_data):
        photo = Photo(
            campaign_id=campaign.campaign_id,
            vendor_id=vendor.vendor_id,
            capture_timestamp=datetime.utcnow() - timedelta(hours=i),
            s3_key=f"test/photo_{i}.jpg",
            verification_status=photo_data['status'],
            location_match_score=photo_data['score']
        )
        db_session.add(photo)
        await db_session.flush()
        
        # Add sensor data
        sensor_data = SensorData(
            photo_id=photo.photo_id,
            gps_latitude=photo_data['lat'],
            gps_longitude=photo_data['lon'],
            gps_accuracy=5.0,
            gps_provider='GPS',
            wifi_networks=[
                {'ssid': 'TestWiFi', 'bssid': '00:11:22:33:44:55', 'signal_strength': -45}
            ],
            cell_towers=[
                {'cell_id': 12345, 'lac': 100, 'mcc': 404, 'mnc': 45}
            ]
        )
        db.add(sensor_data)
        
        # Add audit log for flagged photo
        if photo_data['status'] == VerificationStatus.FLAGGED:
            audit_log = AuditLog(
                vendor_id=vendor.vendor_id,
                photo_id=photo.photo_id,
                campaign_code=campaign.campaign_code,
                sensor_data={'gps': {'lat': photo_data['lat'], 'lon': photo_data['lon']}},
                signature={'valid': True},
                device_info={'model': 'Test Device'},
                record_hash='test_hash',
                audit_flags=['location_mismatch']
            )
            db.add(audit_log)
    
    await db.commit()
    await db.refresh(campaign)
    
    return campaign


class TestCSVExport:
    """Test CSV export functionality."""
    
    async def test_csv_export_success(
        self,
        async_client: AsyncClient,
        test_campaign_with_photos: Campaign,
        auth_headers: dict
    ):
        """Test successful CSV export."""
        response = await async_client.get(
            f"/api/reports/campaigns/{test_campaign_with_photos.campaign_code}/csv",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.headers['content-type'] == 'text/csv; charset=utf-8'
        assert 'attachment' in response.headers['content-disposition']
        
        # Parse CSV content
        csv_content = response.text
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)
        
        # Verify CSV structure
        assert len(rows) == 4  # 4 photos
        
        # Check headers
        expected_headers = [
            'Photo ID', 'Capture Timestamp', 'Upload Timestamp', 'Vendor ID',
            'Verification Status', 'Location Match Score', 'Distance From Expected (m)',
            'GPS Latitude', 'GPS Longitude', 'GPS Accuracy (m)', 'GPS Altitude (m)',
            'GPS Provider', 'GPS Satellites', 'WiFi Networks Count', 'Cell Towers Count',
            'Barometer Pressure (hPa)', 'Ambient Light (lux)', 'Hand Tremor Detected',
            'Confidence Score', 'Audit Flags', 'S3 Key'
        ]
        assert list(rows[0].keys()) == expected_headers
        
        # Verify GPS precision (7 decimal places)
        first_row = rows[0]
        assert len(first_row['GPS Latitude'].split('.')[-1]) == 7
        assert len(first_row['GPS Longitude'].split('.')[-1]) == 7
        
        # Verify data content
        assert first_row['Vendor ID'] == 'VND001'
        assert first_row['GPS Provider'] == 'GPS'
        assert first_row['WiFi Networks Count'] == '1'
        assert first_row['Cell Towers Count'] == '1'
    
    async def test_csv_export_campaign_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test CSV export with non-existent campaign."""
        response = await async_client.get(
            "/api/reports/campaigns/NONEXISTENT/csv",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert 'not found' in response.json()['detail'].lower()


class TestGeoJSONExport:
    """Test GeoJSON export functionality."""
    
    async def test_geojson_export_success(
        self,
        async_client: AsyncClient,
        test_campaign_with_photos: Campaign,
        auth_headers: dict
    ):
        """Test successful GeoJSON export."""
        response = await async_client.get(
            f"/api/reports/campaigns/{test_campaign_with_photos.campaign_code}/geojson",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.headers['content-type'] == 'application/json'
        assert 'attachment' in response.headers['content-disposition']
        
        # Parse GeoJSON
        geojson_data = response.json()
        
        # Verify GeoJSON structure
        assert geojson_data['type'] == 'FeatureCollection'
        assert 'features' in geojson_data
        assert len(geojson_data['features']) == 4
        
        # Check first feature
        first_feature = geojson_data['features'][0]
        assert first_feature['type'] == 'Feature'
        assert first_feature['geometry']['type'] == 'Point'
        assert len(first_feature['geometry']['coordinates']) == 2
        
        # Verify properties
        props = first_feature['properties']
        assert 'photo_id' in props
        assert 'timestamp' in props
        assert 'verification_status' in props
        assert 'vendor_id' in props
        assert 'gps_accuracy' in props
        assert props['vendor_id'] == 'VND001'
    
    async def test_geojson_export_campaign_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test GeoJSON export with non-existent campaign."""
        response = await async_client.get(
            "/api/reports/campaigns/NONEXISTENT/geojson",
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestPDFExport:
    """Test PDF export functionality."""
    
    async def test_pdf_export_success(
        self,
        async_client: AsyncClient,
        test_campaign_with_photos: Campaign,
        auth_headers: dict
    ):
        """Test successful PDF export."""
        response = await async_client.get(
            f"/api/reports/campaigns/{test_campaign_with_photos.campaign_code}/pdf",
            headers=auth_headers
        )
        
        # PDF generation might fail if reportlab is not installed
        if response.status_code == 500 and 'ReportLab' in response.json()['detail']:
            pytest.skip("ReportLab not installed")
        
        assert response.status_code == 200
        assert response.headers['content-type'] == 'application/pdf'
        assert 'attachment' in response.headers['content-disposition']
        
        # Verify PDF content starts with PDF magic bytes
        pdf_content = response.content
        assert pdf_content.startswith(b'%PDF')
        
        # Verify PDF has reasonable size (not empty)
        assert len(pdf_content) > 1000
    
    async def test_pdf_export_campaign_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test PDF export with non-existent campaign."""
        response = await async_client.get(
            "/api/reports/campaigns/NONEXISTENT/pdf",
            headers=auth_headers
        )
        
        # Skip if ReportLab not installed
        if response.status_code == 500 and 'ReportLab' in response.json()['detail']:
            pytest.skip("ReportLab not installed")
        
        assert response.status_code == 404


class TestStatisticsEndpoint:
    """Test campaign statistics endpoint."""
    
    async def test_statistics_success(
        self,
        async_client: AsyncClient,
        test_campaign_with_photos: Campaign,
        auth_headers: dict
    ):
        """Test successful statistics retrieval."""
        response = await async_client.get(
            f"/api/reports/campaigns/{test_campaign_with_photos.campaign_code}/statistics",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        stats = response.json()
        
        # Verify structure
        assert 'campaign' in stats
        assert 'statistics' in stats
        assert 'raw_data' in stats
        
        # Verify campaign info
        assert stats['campaign']['code'] == test_campaign_with_photos.campaign_code
        assert stats['campaign']['name'] == test_campaign_with_photos.name
        
        # Verify statistics
        assert stats['statistics']['total_photos'] == 4
        assert 'status_counts' in stats['statistics']
        assert stats['statistics']['status_counts']['verified'] == 2
        assert stats['statistics']['status_counts']['flagged'] == 1
        assert stats['statistics']['status_counts']['pending'] == 1
        assert stats['statistics']['flagged_photos'] == 1
        
        # Verify average confidence
        assert 'average_confidence' in stats['statistics']
        assert stats['statistics']['average_confidence'] > 0


class TestChartsEndpoint:
    """Test chart generation endpoints."""
    
    async def test_verification_chart_json(
        self,
        async_client: AsyncClient,
        test_campaign_with_photos: Campaign,
        auth_headers: dict
    ):
        """Test verification status chart in JSON format."""
        response = await async_client.get(
            f"/api/reports/campaigns/{test_campaign_with_photos.campaign_code}/charts/verification?format=json",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.headers['content-type'] == 'application/json'
        
        # Verify it's valid JSON
        chart_data = response.json()
        assert 'data' in chart_data
    
    async def test_confidence_chart_json(
        self,
        async_client: AsyncClient,
        test_campaign_with_photos: Campaign,
        auth_headers: dict
    ):
        """Test confidence score chart in JSON format."""
        response = await async_client.get(
            f"/api/reports/campaigns/{test_campaign_with_photos.campaign_code}/charts/confidence?format=json",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.headers['content-type'] == 'application/json'
    
    async def test_timeline_chart_json(
        self,
        async_client: AsyncClient,
        test_campaign_with_photos: Campaign,
        auth_headers: dict
    ):
        """Test timeline chart in JSON format."""
        response = await async_client.get(
            f"/api/reports/campaigns/{test_campaign_with_photos.campaign_code}/charts/timeline?format=json",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.headers['content-type'] == 'application/json'
    
    async def test_invalid_chart_type(
        self,
        async_client: AsyncClient,
        test_campaign_with_photos: Campaign,
        auth_headers: dict
    ):
        """Test invalid chart type."""
        response = await async_client.get(
            f"/api/reports/campaigns/{test_campaign_with_photos.campaign_code}/charts/invalid?format=json",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert 'Invalid chart type' in response.json()['detail']
    
    async def test_invalid_format(
        self,
        async_client: AsyncClient,
        test_campaign_with_photos: Campaign,
        auth_headers: dict
    ):
        """Test invalid format."""
        response = await async_client.get(
            f"/api/reports/campaigns/{test_campaign_with_photos.campaign_code}/charts/verification?format=invalid",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert 'Invalid format' in response.json()['detail']


class TestDashboardEndpoint:
    """Test dashboard endpoint that combines all data."""
    
    async def test_dashboard_success(
        self,
        async_client: AsyncClient,
        test_campaign_with_photos: Campaign,
        auth_headers: dict
    ):
        """Test successful dashboard data retrieval."""
        response = await async_client.get(
            f"/api/reports/campaigns/{test_campaign_with_photos.campaign_code}/dashboard",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        dashboard = response.json()
        
        # Verify all components are present
        assert 'statistics' in dashboard
        assert 'charts' in dashboard
        assert 'map' in dashboard
        
        # Verify statistics
        assert dashboard['statistics']['statistics']['total_photos'] == 4
        
        # Verify charts
        assert 'verification' in dashboard['charts']
        assert 'confidence' in dashboard['charts']
        assert 'timeline' in dashboard['charts']
        
        # Verify map (GeoJSON)
        assert dashboard['map']['type'] == 'FeatureCollection'
        assert len(dashboard['map']['features']) == 4
