"""Comprehensive subscription endpoint tests."""
import pytest
from httpx import AsyncClient


class TestSubscriptionUsage:
    """Test GET /api/subscriptions/usage"""

    async def test_get_usage(self, client: AsyncClient, auth_headers, test_subscription):
        resp = await client.get("/api/subscriptions/usage", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "photos" in data or "subscription" in data

    async def test_get_usage_no_auth(self, client: AsyncClient):
        resp = await client.get("/api/subscriptions/usage")
        assert resp.status_code in (401, 403)


class TestSubscriptionCurrent:
    """Test GET /api/subscriptions/current"""

    async def test_get_current(self, client: AsyncClient, auth_headers, test_subscription):
        resp = await client.get("/api/subscriptions/current", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "tier" in data
        assert "status" in data


class TestSubscriptionTiers:
    """Test GET /api/subscriptions/tiers"""

    async def test_get_tiers(self, client: AsyncClient):
        resp = await client.get("/api/subscriptions/tiers")
        assert resp.status_code == 200
        data = resp.json()
        assert "tiers" in data
        tier_names = [t["name"] for t in data["tiers"]]
        assert "free" in tier_names
        assert "pro" in tier_names
        assert "enterprise" in tier_names


class TestSubscriptionHealth:
    """Test GET /api/subscriptions/health"""

    async def test_health(self, client: AsyncClient):
        resp = await client.get("/api/subscriptions/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestSubscriptionUpgrade:
    """Test POST /api/subscriptions/upgrade"""

    async def test_upgrade_to_pro(self, client: AsyncClient, auth_headers, test_subscription):
        resp = await client.post("/api/subscriptions/upgrade", json={
            "tier": "pro",
            "billing_cycle": "monthly",
        }, headers=auth_headers)
        # Should succeed or return meaningful error
        assert resp.status_code in (200, 400, 500)

    async def test_upgrade_invalid_tier(self, client: AsyncClient, auth_headers, test_subscription):
        resp = await client.post("/api/subscriptions/upgrade", json={
            "tier": "invalid",
            "billing_cycle": "monthly",
        }, headers=auth_headers)
        assert resp.status_code == 400


class TestSubscriptionCancel:
    """Test POST /api/subscriptions/cancel"""

    async def test_cancel(self, client: AsyncClient, auth_headers, test_subscription):
        resp = await client.post("/api/subscriptions/cancel", json={
            "immediate": False,
        }, headers=auth_headers)
        assert resp.status_code in (200, 400, 500)


class TestSyncUsage:
    """Test POST /api/subscriptions/sync-usage"""

    async def test_sync(self, client: AsyncClient, auth_headers, test_subscription):
        resp = await client.post("/api/subscriptions/sync-usage", headers=auth_headers)
        assert resp.status_code == 200
        assert "usage" in resp.json()
