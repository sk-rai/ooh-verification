"""Comprehensive admin endpoint tests."""
import pytest
from httpx import AsyncClient


class TestAdminLogin:
    """Test POST /api/admin/login"""

    async def test_admin_login_success(self, client: AsyncClient, test_admin):
        resp = await client.post("/api/admin/login", json={
            "email": "admin@trustcapture.com",
            "password": "TrustAdmin@2026",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_admin_login_wrong_password(self, client: AsyncClient, test_admin):
        resp = await client.post("/api/admin/login", json={
            "email": "admin@trustcapture.com",
            "password": "WrongPassword",
        })
        assert resp.status_code == 401

    async def test_admin_login_nonexistent(self, client: AsyncClient):
        resp = await client.post("/api/admin/login", json={
            "email": "nobody@admin.com",
            "password": "Whatever",
        })
        assert resp.status_code == 401


class TestAdminMe:
    """Test GET /api/admin/me"""

    async def test_admin_profile(self, client: AsyncClient, admin_auth_headers, test_admin):
        resp = await client.get("/api/admin/me", headers=admin_auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "admin@trustcapture.com"

    async def test_admin_profile_no_auth(self, client: AsyncClient):
        resp = await client.get("/api/admin/me")
        assert resp.status_code in (401, 403)


class TestAdminDashboard:
    """Test GET /api/admin/dashboard"""

    async def test_dashboard(self, client: AsyncClient, admin_auth_headers, test_admin, test_client_user, test_tenant):
        resp = await client.get("/api/admin/dashboard", headers=admin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "overview" in data
        assert "clients" in data
        assert "usage" in data
        assert data["overview"]["total_clients"] >= 1
