"""Tests for vendor-facing campaign endpoints."""
import pytest
from httpx import AsyncClient
from app.models.campaign_vendor_assignment import CampaignVendorAssignment


class TestVendorMyCampaigns:
    """Test GET /api/vendors/me/campaigns"""

    async def test_get_my_campaigns_empty(self, client: AsyncClient, vendor_auth_headers):
        resp = await client.get("/api/vendors/me/campaigns", headers=vendor_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "campaigns" in data
        assert data["total"] == 0

    async def test_get_my_campaigns_with_assignment(
        self, client: AsyncClient, vendor_auth_headers,
        test_vendor, test_campaign, db_session,
    ):
        assignment = CampaignVendorAssignment(
            campaign_id=test_campaign.campaign_id,
            vendor_id=test_vendor.vendor_id,
        )
        db_session.add(assignment)
        await db_session.flush()
        resp = await client.get("/api/vendors/me/campaigns", headers=vendor_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert data["campaigns"][0]["campaign_code"] == test_campaign.campaign_code
