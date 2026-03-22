"""Tests for health check and root endpoints."""
import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    """Test basic app endpoints."""

    async def test_health_check(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    async def test_root(self, client: AsyncClient):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert data["message"] == "TrustCapture API"
