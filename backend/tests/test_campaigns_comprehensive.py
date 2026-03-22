"""Comprehensive campaign endpoint tests."""
import pytest
import uuid
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


class TestCreateCampaign:
    """Test POST /api/campaigns"""

    async def test_create_campaign_basic(self, client: AsyncClient, auth_headers, test_subscription):
        resp = await client.post("/api/campaigns", json={
            "name": "Billboard NYC",
            "campaign_type": "ooh",
            "start_date": (datetime.now(tz=timezone.utc)).isoformat(),
            "end_date": (datetime.now(tz=timezone.utc) + timedelta(days=30)).isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Billboard NYC"
        assert data["campaign_type"] == "ooh"
        assert data["status"] == "active"
        assert "campaign_code" in data

    async def test_create_campaign_with_location_profile(self, client: AsyncClient, auth_headers, test_subscription):
        """Test campaign creation with location profile and auto-population of pressure/magnetic."""
        with patch("app.api.campaigns.get_pressure_range", new_callable=AsyncMock, return_value=(997.0, 1027.0)), \
             patch("app.api.campaigns.get_magnetic_field_range", new_callable=AsyncMock, return_value=(33.0, 53.0)):
            resp = await client.post("/api/campaigns", json={
                "name": "Mumbai Billboard",
                "campaign_type": "ooh",
                "start_date": datetime.now(tz=timezone.utc).isoformat(),
                "end_date": (datetime.now(tz=timezone.utc) + timedelta(days=30)).isoformat(),
                "location_profile": {
                    "expected_latitude": 19.076,
                    "expected_longitude": 72.8777,
                    "tolerance_meters": 50.0,
                },
            }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        lp = data.get("location_profile")
        assert lp is not None
        assert lp["expected_latitude"] == pytest.approx(19.076, abs=0.001)
        # Pressure and magnetic should be auto-populated
        assert lp["expected_pressure_min"] == pytest.approx(997.0, abs=1)
        assert lp["expected_pressure_max"] == pytest.approx(1027.0, abs=1)
        assert lp["expected_magnetic_min"] == pytest.approx(33.0, abs=1)
        assert lp["expected_magnetic_max"] == pytest.approx(53.0, abs=1)

    async def test_create_campaign_with_explicit_pressure(self, client: AsyncClient, auth_headers, test_subscription):
        """When pressure is explicitly provided, auto-population should NOT override."""
        with patch("app.api.campaigns.get_pressure_range", new_callable=AsyncMock) as mock_pr, \
             patch("app.api.campaigns.get_magnetic_field_range", new_callable=AsyncMock, return_value=None):
            resp = await client.post("/api/campaigns", json={
                "name": "Explicit Pressure Campaign",
                "campaign_type": "construction",
                "start_date": datetime.now(tz=timezone.utc).isoformat(),
                "end_date": (datetime.now(tz=timezone.utc) + timedelta(days=10)).isoformat(),
                "location_profile": {
                    "expected_latitude": 28.6139,
                    "expected_longitude": 77.2090,
                    "tolerance_meters": 100.0,
                    "expected_pressure_min": 990.0,
                    "expected_pressure_max": 1010.0,
                },
            }, headers=auth_headers)
        assert resp.status_code == 201
        lp = resp.json()["location_profile"]
        assert lp["expected_pressure_min"] == 990.0
        assert lp["expected_pressure_max"] == 1010.0
        mock_pr.assert_not_called()

    async def test_create_campaign_invalid_type(self, client: AsyncClient, auth_headers, test_subscription):
        resp = await client.post("/api/campaigns", json={
            "name": "Bad Type",
            "campaign_type": "invalid_type",
            "start_date": datetime.now(tz=timezone.utc).isoformat(),
            "end_date": (datetime.now(tz=timezone.utc) + timedelta(days=5)).isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 422

    async def test_create_campaign_end_before_start(self, client: AsyncClient, auth_headers, test_subscription):
        resp = await client.post("/api/campaigns", json={
            "name": "Bad Dates",
            "campaign_type": "ooh",
            "start_date": (datetime.now(tz=timezone.utc) + timedelta(days=10)).isoformat(),
            "end_date": datetime.now(tz=timezone.utc).isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 422


class TestListCampaigns:
    """Test GET /api/campaigns"""

    async def test_list_campaigns(self, client: AsyncClient, auth_headers, test_campaign, test_subscription):
        resp = await client.get("/api/campaigns", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "campaigns" in data
        assert "total" in data

    async def test_list_campaigns_filter_type(self, client: AsyncClient, auth_headers, test_campaign, test_subscription):
        resp = await client.get("/api/campaigns?campaign_type=ooh", headers=auth_headers)
        assert resp.status_code == 200


class TestGetCampaign:
    """Test GET /api/campaigns/{campaign_id}"""

    async def test_get_campaign(self, client: AsyncClient, auth_headers, test_campaign, test_subscription):
        resp = await client.get(f"/api/campaigns/{test_campaign.campaign_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["campaign_id"] == str(test_campaign.campaign_id)

    async def test_get_nonexistent_campaign(self, client: AsyncClient, auth_headers, test_subscription):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/campaigns/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404


class TestUpdateCampaign:
    """Test PATCH /api/campaigns/{campaign_id}"""

    async def test_update_campaign_name(self, client: AsyncClient, auth_headers, test_campaign, test_subscription):
        resp = await client.patch(f"/api/campaigns/{test_campaign.campaign_id}", json={
            "name": "Updated Campaign Name",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Campaign Name"

    async def test_update_campaign_status(self, client: AsyncClient, auth_headers, test_campaign, test_subscription):
        resp = await client.patch(f"/api/campaigns/{test_campaign.campaign_id}", json={
            "status": "completed",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"


class TestVendorAssignment:
    """Test POST/DELETE /api/campaigns/{id}/vendors"""

    async def test_assign_vendor_to_campaign(self, client: AsyncClient, auth_headers, test_campaign, test_vendor, test_subscription):
        resp = await client.post(f"/api/campaigns/{test_campaign.campaign_id}/vendors", json={
            "vendor_ids": [test_vendor.vendor_id],
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 1
        assert data[0]["vendor_id"] == test_vendor.vendor_id

    async def test_assign_duplicate_vendor(self, client: AsyncClient, auth_headers, test_campaign, test_vendor, test_subscription, db_session):
        from app.models.campaign_vendor_assignment import CampaignVendorAssignment
        assignment = CampaignVendorAssignment(campaign_id=test_campaign.campaign_id, vendor_id=test_vendor.vendor_id)
        db_session.add(assignment)
        await db_session.flush()
        resp = await client.post(f"/api/campaigns/{test_campaign.campaign_id}/vendors", json={
            "vendor_ids": [test_vendor.vendor_id],
        }, headers=auth_headers)
        assert resp.status_code == 400

    async def test_remove_vendor_from_campaign(self, client: AsyncClient, auth_headers, test_campaign, test_vendor, test_subscription, db_session):
        from app.models.campaign_vendor_assignment import CampaignVendorAssignment
        assignment = CampaignVendorAssignment(campaign_id=test_campaign.campaign_id, vendor_id=test_vendor.vendor_id)
        db_session.add(assignment)
        await db_session.flush()
        resp = await client.delete(f"/api/campaigns/{test_campaign.campaign_id}/vendors/{test_vendor.vendor_id}", headers=auth_headers)
        assert resp.status_code == 204
