"""Tests for Pydantic schemas validation."""
import pytest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError
from app.schemas.photo import (
    GPSData, SensorDataSchema, PhotoSignatureSchema, EnvironmentalData,
)
from app.schemas.campaign import CampaignCreate, LocationProfileCreate


class TestGPSData:
    def test_valid_gps(self):
        gps = GPSData(latitude=19.076, longitude=72.8777)
        assert gps.latitude == 19.076

    def test_invalid_latitude(self):
        with pytest.raises(ValidationError):
            GPSData(latitude=100.0, longitude=0.0)

    def test_invalid_longitude(self):
        with pytest.raises(ValidationError):
            GPSData(latitude=0.0, longitude=200.0)


class TestSensorDataSchema:
    def test_minimal_sensor_data(self):
        sd = SensorDataSchema(gps=GPSData(latitude=19.076, longitude=72.8777))
        assert sd.gps.latitude == 19.076
        assert sd.wifi_networks is None
        assert sd.cell_towers is None

    def test_with_environmental(self):
        sd = SensorDataSchema(
            gps=GPSData(latitude=19.076, longitude=72.8777),
            environmental=EnvironmentalData(
                barometer_pressure=1012.5,
                magnetic_field_magnitude=43.5,
                hand_tremor_frequency=10.0,
                hand_tremor_is_human=True,
                hand_tremor_confidence=0.9,
            ),
        )
        assert sd.environmental.barometer_pressure == 1012.5
        assert sd.environmental.magnetic_field_magnitude == 43.5


class TestPhotoSignatureSchema:
    def test_valid_signature(self):
        sig = PhotoSignatureSchema(
            signature="base64data==",
            algorithm="ECDSA-P256",
            timestamp=datetime.now(tz=timezone.utc),
            location_hash="abc123",
            device_id="device-001",
        )
        assert sig.algorithm == "ECDSA-P256"

    def test_invalid_algorithm(self):
        with pytest.raises(ValidationError):
            PhotoSignatureSchema(
                signature="base64data==",
                algorithm="INVALID-ALG",
                timestamp=datetime.now(tz=timezone.utc),
                location_hash="abc123",
                device_id="device-001",
            )


class TestCampaignCreate:
    def test_valid_campaign(self):
        c = CampaignCreate(
            name="Test",
            campaign_type="ooh",
            start_date=datetime.now(tz=timezone.utc),
            end_date=datetime.now(tz=timezone.utc) + timedelta(days=30),
        )
        assert c.campaign_type == "ooh"

    def test_invalid_campaign_type(self):
        with pytest.raises(ValidationError):
            CampaignCreate(
                name="Test",
                campaign_type="invalid",
                start_date=datetime.now(tz=timezone.utc),
                end_date=datetime.now(tz=timezone.utc) + timedelta(days=30),
            )

    def test_end_before_start(self):
        with pytest.raises(ValidationError):
            CampaignCreate(
                name="Test",
                campaign_type="ooh",
                start_date=datetime.now(tz=timezone.utc) + timedelta(days=30),
                end_date=datetime.now(tz=timezone.utc),
            )

    def test_with_location_profile(self):
        c = CampaignCreate(
            name="Test",
            campaign_type="ooh",
            start_date=datetime.now(tz=timezone.utc),
            end_date=datetime.now(tz=timezone.utc) + timedelta(days=30),
            location_profile=LocationProfileCreate(
                expected_latitude=19.076,
                expected_longitude=72.8777,
                tolerance_meters=50.0,
                expected_pressure_min=997.0,
                expected_pressure_max=1027.0,
                expected_magnetic_min=33.0,
                expected_magnetic_max=53.0,
            ),
        )
        assert c.location_profile.expected_pressure_min == 997.0
