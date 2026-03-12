"""
Integration tests for photo upload API.

Tests photo upload with signature verification and location matching.
"""
import pytest
import json
import base64
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
from unittest.mock import patch, MagicMock
import uuid

from app.models import Photo, SensorData, PhotoSignature, Campaign, Vendor, LocationProfile
from app.models.photo import VerificationStatus
from app.models.campaign import CampaignStatus, CampaignType
from app.models.vendor import VendorStatus
from app.models.campaign_vendor_assignment import CampaignVendorAssignment


def create_test_jpeg() -> bytes:
    """Create a test JPEG image."""
    img = Image.new('RGB', (800, 600), color='red')
    img_bytes = BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes.read()


def create_sensor_data_json() -> str:
    """Create test sensor data JSON."""
    sensor_data = {
        "gps": {
            "latitude": 40.7580,
            "longitude": -73.9855,
            "altitude": 10.5,
            "accuracy": 5.0,
            "provider": "GPS",
            "satellite_count": 12
        },
        "wifi_networks": [
            {
                "ssid": "TestNetwork",
                "bssid": "00:11:22:33:44:55",
                "signal_strength": -45,
                "frequency": 2437
            }
        ],
        "cell_towers": [
            {
                "cell_id": 12345,
                "lac": 100,
                "mcc": 310,
                "mnc": 260,
                "signal_strength": -75,
                "network_type": "LTE"
            }
        ],
        "environmental": {
            "barometer_pressure": 1013.25,
            "ambient_light_lux": 250.0
        },
        "location_hash": "test_hash_123",
        "confidence_score": 0.95,
        "schema_version": "2.0"
    }
    return json.dumps(sensor_data)


def create_signature_json(device_id: str = "test-device-123") -> str:
    """Create test signature JSON."""
    signature = {
        "signature": base64.b64encode(b"test_signature_data").decode(),
        "algorithm": "RSA-2048",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "location_hash": "test_hash_123",
        "device_id": device_id
    }
    return json.dumps(signature)


@pytest.fixture
async def test_campaign(db_session, test_client_user):
    """Create a test campaign."""
    campaign = Campaign(
        campaign_id=uuid.uuid4(),
        campaign_code="TEST-2026-ABC",
        name="Test Campaign",
        campaign_type=CampaignType.OOH_ADVERTISING,
        client_id=test_client_user.client_id,
        start_date=datetime.utcnow() - timedelta(days=1),
        end_date=datetime.utcnow() + timedelta(days=30),
        status=CampaignStatus.ACTIVE,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(campaign)
    await db_session.commit()
    await db_session.refresh(campaign)
    return campaign


@pytest.fixture
async def test_vendor_with_key(db_session, test_client_user):
    """Create a test vendor with public key."""
    vendor = Vendor(
        vendor_id="TST123",
        created_by_client_id=test_client_user.client_id,
        phone_number="+1234567890",
        name="Test Vendor",
        status=VendorStatus.ACTIVE,
        device_id="test-device-123",
        public_key="-----BEGIN PUBLIC KEY-----\ntest_key\n-----END PUBLIC KEY-----",
        created_at=datetime.utcnow()
    )
    db_session.add(vendor)
    await db_session.commit()
    await db_session.refresh(vendor)
    return vendor


@pytest.fixture
async def campaign_vendor_assignment(db_session, test_campaign, test_vendor_with_key):
    """Create campaign-vendor assignment."""
    assignment = CampaignVendorAssignment(
        assignment_id=uuid.uuid4(),
        campaign_id=test_campaign.campaign_id,
        vendor_id=test_vendor_with_key.vendor_id,
        assigned_at=datetime.utcnow()
    )
    db_session.add(assignment)
    await db_session.commit()
    return assignment


@pytest.fixture
async def test_location_profile(db_session, test_campaign):
    """Create a test location profile."""
    profile = LocationProfile(
        profile_id=uuid.uuid4(),
        campaign_id=test_campaign.campaign_id,
        expected_latitude=40.7580,
        expected_longitude=-73.9855,
        tolerance_meters=50.0,
        expected_wifi_bssids=["00:11:22:33:44:55"],
        expected_cell_tower_ids=[12345],
        expected_pressure_min=1010.0,
        expected_pressure_max=1020.0,
        expected_light_min=100.0,
        expected_light_max=500.0,
        created_at=datetime.utcnow()
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


@pytest.mark.asyncio
async def test_upload_photo_success_with_valid_signature(
    client,
    db_session,
    test_campaign,
    test_vendor_with_key,
    campaign_vendor_assignment,
    vendor_token
):
    """
    Test successful photo upload with valid signature.
    
    Requirements: 9.1, 9.2, 9.7
    """
    # Mock S3 upload
    with patch('app.services.s3_storage.s3_storage_service.upload_photo_with_thumbnail') as mock_s3:
        mock_s3.return_value = (
            "photos/test/photo.jpg",
            "http://localhost:4566/bucket/photos/test/photo.jpg",
            "thumbnails/test/photo.jpg",
            "http://localhost:4566/bucket/thumbnails/test/photo.jpg"
        )
        
        # Mock signature verification
        with patch('app.services.signature_verification.SignatureVerificationService.verify_signature') as mock_verify:
            mock_verify.return_value = True
            
            # Prepare upload data
            photo_bytes = create_test_jpeg()
            sensor_data = create_sensor_data_json()
            signature = create_signature_json(test_vendor_with_key.device_id)
            capture_timestamp = datetime.utcnow().isoformat() + "Z"
            
            # Upload photo
            response = await client.post(
                "/api/photos/upload",
                headers={"Authorization": f"Bearer {vendor_token}"},
                data={
                    "sensor_data": sensor_data,
                    "signature": signature,
                    "campaign_code": test_campaign.campaign_code,
                    "capture_timestamp": capture_timestamp
                },
                files={"photo": ("test.jpg", photo_bytes, "image/jpeg")}
            )
            
            assert response.status_code == 201
            data = response.json()
            
            assert "photo_id" in data
            assert data["verification_status"] == "verified"
            assert data["signature_valid"] is True
            assert "s3_url" in data
            assert "thumbnail_url" in data
            
            # Verify database records
            from sqlalchemy import select
            result = await db_session.execute(
                select(Photo).where(Photo.photo_id == data["photo_id"])
            )
            photo = result.scalar_one_or_none()
            assert photo is not None
            assert photo.verification_status == VerificationStatus.VERIFIED
            assert photo.signature_valid is True


@pytest.mark.asyncio
async def test_upload_photo_rejected_invalid_signature(
    client,
    db_session,
    test_campaign,
    test_vendor_with_key,
    campaign_vendor_assignment,
    vendor_token
):
    """
    Test photo upload rejection with invalid signature.
    
    Requirements: 9.2, 9.7
    """
    # Mock S3 upload
    with patch('app.services.s3_storage.s3_storage_service.upload_photo_with_thumbnail') as mock_s3:
        mock_s3.return_value = (
            "photos/test/photo.jpg",
            "http://localhost:4566/bucket/photos/test/photo.jpg",
            "thumbnails/test/photo.jpg",
            "http://localhost:4566/bucket/thumbnails/test/photo.jpg"
        )
        
        # Mock signature verification to fail
        with patch('app.services.signature_verification.SignatureVerificationService.verify_signature') as mock_verify:
            mock_verify.return_value = False
            
            # Prepare upload data
            photo_bytes = create_test_jpeg()
            sensor_data = create_sensor_data_json()
            signature = create_signature_json(test_vendor_with_key.device_id)
            capture_timestamp = datetime.utcnow().isoformat() + "Z"
            
            # Upload photo
            response = await client.post(
                "/api/photos/upload",
                headers={"Authorization": f"Bearer {vendor_token}"},
                data={
                    "sensor_data": sensor_data,
                    "signature": signature,
                    "campaign_code": test_campaign.campaign_code,
                    "capture_timestamp": capture_timestamp
                },
                files={"photo": ("test.jpg", photo_bytes, "image/jpeg")}
            )
            
            assert response.status_code == 201
            data = response.json()
            
            assert data["verification_status"] == "rejected"
            assert data["signature_valid"] is False


@pytest.mark.asyncio
async def test_upload_photo_with_location_profile_match(
    client,
    db_session,
    test_campaign,
    test_vendor_with_key,
    campaign_vendor_assignment,
    test_location_profile,
    vendor_token
):
    """
    Test photo upload with location profile matching (verified).
    
    Requirements: 7.5, 7.6, 9.7
    """
    # Mock S3 upload
    with patch('app.services.s3_storage.s3_storage_service.upload_photo_with_thumbnail') as mock_s3:
        mock_s3.return_value = (
            "photos/test/photo.jpg",
            "http://localhost:4566/bucket/photos/test/photo.jpg",
            "thumbnails/test/photo.jpg",
            "http://localhost:4566/bucket/thumbnails/test/photo.jpg"
        )
        
        # Mock signature verification
        with patch('app.services.signature_verification.SignatureVerificationService.verify_signature') as mock_verify:
            mock_verify.return_value = True
            
            # Mock location matcher to return high score
            with patch('app.services.location_profile_matcher.LocationProfileMatcher.match_location') as mock_match:
                mock_match.return_value = {
                    'match_score': 95.0,
                    'distance_meters': 10.5,
                    'details': {}
                }
                
                # Prepare upload data
                photo_bytes = create_test_jpeg()
                sensor_data = create_sensor_data_json()
                signature = create_signature_json(test_vendor_with_key.device_id)
                capture_timestamp = datetime.utcnow().isoformat() + "Z"
                
                # Upload photo
                response = await client.post(
                    "/api/photos/upload",
                    headers={"Authorization": f"Bearer {vendor_token}"},
                    data={
                        "sensor_data": sensor_data,
                        "signature": signature,
                        "campaign_code": test_campaign.campaign_code,
                        "capture_timestamp": capture_timestamp
                    },
                    files={"photo": ("test.jpg", photo_bytes, "image/jpeg")}
                )
                
                assert response.status_code == 201
                data = response.json()
                
                assert data["verification_status"] == "verified"
                assert data["signature_valid"] is True
                assert data["location_match_score"] == 95.0
                assert data["distance_from_expected"] == 10.5


@pytest.mark.asyncio
async def test_upload_photo_with_location_profile_mismatch(
    client,
    db_session,
    test_campaign,
    test_vendor_with_key,
    campaign_vendor_assignment,
    test_location_profile,
    vendor_token
):
    """
    Test photo upload with location profile mismatch (flagged).
    
    Requirements: 7.5, 7.6, 27.2
    """
    # Mock S3 upload
    with patch('app.services.s3_storage.s3_storage_service.upload_photo_with_thumbnail') as mock_s3:
        mock_s3.return_value = (
            "photos/test/photo.jpg",
            "http://localhost:4566/bucket/photos/test/photo.jpg",
            "thumbnails/test/photo.jpg",
            "http://localhost:4566/bucket/thumbnails/test/photo.jpg"
        )
        
        # Mock signature verification
        with patch('app.services.signature_verification.SignatureVerificationService.verify_signature') as mock_verify:
            mock_verify.return_value = True
            
            # Mock location matcher to return low score
            with patch('app.services.location_profile_matcher.LocationProfileMatcher.match_location') as mock_match:
                mock_match.return_value = {
                    'match_score': 35.0,
                    'distance_meters': 500.0,
                    'details': {}
                }
                
                # Prepare upload data
                photo_bytes = create_test_jpeg()
                sensor_data = create_sensor_data_json()
                signature = create_signature_json(test_vendor_with_key.device_id)
                capture_timestamp = datetime.utcnow().isoformat() + "Z"
                
                # Upload photo
                response = await client.post(
                    "/api/photos/upload",
                    headers={"Authorization": f"Bearer {vendor_token}"},
                    data={
                        "sensor_data": sensor_data,
                        "signature": signature,
                        "campaign_code": test_campaign.campaign_code,
                        "capture_timestamp": capture_timestamp
                    },
                    files={"photo": ("test.jpg", photo_bytes, "image/jpeg")}
                )
                
                assert response.status_code == 201
                data = response.json()
                
                assert data["verification_status"] == "flagged"
                assert data["signature_valid"] is True
                assert data["location_match_score"] == 35.0


@pytest.mark.asyncio
async def test_upload_photo_without_location_profile(
    client,
    db_session,
    test_campaign,
    test_vendor_with_key,
    campaign_vendor_assignment,
    vendor_token
):
    """
    Test photo upload without location profile (verified if signature valid).
    
    Requirements: 9.1, 9.7
    """
    # Mock S3 upload
    with patch('app.services.s3_storage.s3_storage_service.upload_photo_with_thumbnail') as mock_s3:
        mock_s3.return_value = (
            "photos/test/photo.jpg",
            "http://localhost:4566/bucket/photos/test/photo.jpg",
            "thumbnails/test/photo.jpg",
            "http://localhost:4566/bucket/thumbnails/test/photo.jpg"
        )
        
        # Mock signature verification
        with patch('app.services.signature_verification.SignatureVerificationService.verify_signature') as mock_verify:
            mock_verify.return_value = True
            
            # Prepare upload data
            photo_bytes = create_test_jpeg()
            sensor_data = create_sensor_data_json()
            signature = create_signature_json(test_vendor_with_key.device_id)
            capture_timestamp = datetime.utcnow().isoformat() + "Z"
            
            # Upload photo
            response = await client.post(
                "/api/photos/upload",
                headers={"Authorization": f"Bearer {vendor_token}"},
                data={
                    "sensor_data": sensor_data,
                    "signature": signature,
                    "campaign_code": test_campaign.campaign_code,
                    "capture_timestamp": capture_timestamp
                },
                files={"photo": ("test.jpg", photo_bytes, "image/jpeg")}
            )
            
            assert response.status_code == 201
            data = response.json()
            
            assert data["verification_status"] == "verified"
            assert data["signature_valid"] is True
            assert data["location_match_score"] is None


@pytest.mark.asyncio
async def test_upload_photo_invalid_format(
    client,
    test_campaign,
    test_vendor_with_key,
    campaign_vendor_assignment,
    vendor_token
):
    """
    Test photo upload with invalid format.
    
    Requirements: 9.2
    """
    # Create invalid file (not JPEG)
    invalid_bytes = b"not a jpeg file"
    
    sensor_data = create_sensor_data_json()
    signature = create_signature_json(test_vendor_with_key.device_id)
    capture_timestamp = datetime.utcnow().isoformat() + "Z"
    
    response = await client.post(
        "/api/photos/upload",
        headers={"Authorization": f"Bearer {vendor_token}"},
        data={
            "sensor_data": sensor_data,
            "signature": signature,
            "campaign_code": test_campaign.campaign_code,
            "capture_timestamp": capture_timestamp
        },
        files={"photo": ("test.jpg", invalid_bytes, "image/jpeg")}
    )
    
    assert response.status_code == 400
    assert "Invalid JPEG file" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_photo_file_too_large(
    client,
    test_campaign,
    test_vendor_with_key,
    campaign_vendor_assignment,
    vendor_token
):
    """
    Test photo upload with file too large.
    
    Requirements: 9.2, 21.1
    """
    # Create large file (> 5MB)
    large_bytes = b'\xff\xd8' + b'x' * (6 * 1024 * 1024) + b'\xff\xd9'
    
    sensor_data = create_sensor_data_json()
    signature = create_signature_json(test_vendor_with_key.device_id)
    capture_timestamp = datetime.utcnow().isoformat() + "Z"
    
    response = await client.post(
        "/api/photos/upload",
        headers={"Authorization": f"Bearer {vendor_token}"},
        data={
            "sensor_data": sensor_data,
            "signature": signature,
            "campaign_code": test_campaign.campaign_code,
            "capture_timestamp": capture_timestamp
        },
        files={"photo": ("test.jpg", large_bytes, "image/jpeg")}
    )
    
    assert response.status_code == 400
    assert "File too large" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_photo_invalid_campaign(
    client,
    test_vendor_with_key,
    vendor_token
):
    """
    Test photo upload with invalid campaign code.
    
    Requirements: 21.5
    """
    photo_bytes = create_test_jpeg()
    sensor_data = create_sensor_data_json()
    signature = create_signature_json(test_vendor_with_key.device_id)
    capture_timestamp = datetime.utcnow().isoformat() + "Z"
    
    response = await client.post(
        "/api/photos/upload",
        headers={"Authorization": f"Bearer {vendor_token}"},
        data={
            "sensor_data": sensor_data,
            "signature": signature,
            "campaign_code": "INVALID-CODE",
            "capture_timestamp": capture_timestamp
        },
        files={"photo": ("test.jpg", photo_bytes, "image/jpeg")}
    )
    
    assert response.status_code == 404
    assert "Campaign not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_photo_vendor_not_assigned(
    client,
    db_session,
    test_campaign,
    test_vendor_with_key,
    vendor_token
):
    """
    Test photo upload when vendor not assigned to campaign.
    
    Requirements: 21.5
    """
    # Don't create assignment
    photo_bytes = create_test_jpeg()
    sensor_data = create_sensor_data_json()
    signature = create_signature_json(test_vendor_with_key.device_id)
    capture_timestamp = datetime.utcnow().isoformat() + "Z"
    
    response = await client.post(
        "/api/photos/upload",
        headers={"Authorization": f"Bearer {vendor_token}"},
        data={
            "sensor_data": sensor_data,
            "signature": signature,
            "campaign_code": test_campaign.campaign_code,
            "capture_timestamp": capture_timestamp
        },
        files={"photo": ("test.jpg", photo_bytes, "image/jpeg")}
    )
    
    assert response.status_code == 403
    assert "not assigned" in response.json()["detail"]
