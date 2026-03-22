"""Comprehensive auth endpoint tests."""
import pytest
from httpx import AsyncClient


class TestClientRegistration:
    """Test POST /api/auth/register"""

    async def test_register_new_client(self, client: AsyncClient):
        resp = await client.post("/api/auth/register", json={
            "email": "newclient@example.com",
            "password": "SecurePass123!",
            "company_name": "New Company",
            "phone_number": "+1555000111",
        }, headers={"X-Tenant-ID": "e27c6c7a-7f5b-43df-bdc4-abd76ebb99aa"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newclient@example.com"
        assert data["company_name"] == "New Company"
        assert "client_id" in data

    async def test_register_duplicate_email(self, client: AsyncClient, test_client_user):
        resp = await client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "SecurePass123!",
            "company_name": "Dup Company",
            "phone_number": "+1555000222",
        }, headers={"X-Tenant-ID": "e27c6c7a-7f5b-43df-bdc4-abd76ebb99aa"})
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()


class TestClientLogin:
    """Test POST /api/auth/login"""

    async def test_login_success(self, client: AsyncClient, test_client_user, test_subscription):
        resp = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "Test123!@#",
        }, headers={"X-Tenant-ID": "e27c6c7a-7f5b-43df-bdc4-abd76ebb99aa"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, test_client_user):
        resp = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "WrongPassword",
        }, headers={"X-Tenant-ID": "e27c6c7a-7f5b-43df-bdc4-abd76ebb99aa"})
        assert resp.status_code == 401

    async def test_login_nonexistent_email(self, client: AsyncClient):
        resp = await client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "Whatever123",
        }, headers={"X-Tenant-ID": "e27c6c7a-7f5b-43df-bdc4-abd76ebb99aa"})
        assert resp.status_code == 401


class TestVendorOTP:
    """Test vendor OTP flow."""

    async def test_request_otp_valid_vendor(self, client: AsyncClient, test_vendor, test_tenant):
        resp = await client.post("/api/auth/vendor/request-otp", json={
            "vendor_id": test_vendor.vendor_id,
            "phone_number": test_vendor.phone_number,
        }, headers={"X-Tenant-ID": str(test_tenant.tenant_id)})
        assert resp.status_code == 200
        assert "expires_in" in resp.json()

    async def test_request_otp_invalid_vendor(self, client: AsyncClient, test_tenant):
        resp = await client.post("/api/auth/vendor/request-otp", json={
            "vendor_id": "XXXXXX",
            "phone_number": "+910000000000",
        }, headers={"X-Tenant-ID": str(test_tenant.tenant_id)})
        assert resp.status_code == 404

    async def test_verify_otp_invalid(self, client: AsyncClient, test_vendor, test_tenant):
        resp = await client.post("/api/auth/vendor/verify-otp", json={
            "vendor_id": test_vendor.vendor_id,
            "phone_number": test_vendor.phone_number,
            "otp": "000000",
        }, headers={"X-Tenant-ID": str(test_tenant.tenant_id)})
        assert resp.status_code == 401


class TestAuthMe:
    """Test /api/auth/me/* endpoints."""

    async def test_get_current_client(self, client: AsyncClient, auth_headers, test_subscription):
        resp = await client.get("/api/auth/me/client", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    async def test_get_client_no_auth(self, client: AsyncClient):
        resp = await client.get("/api/auth/me/client")
        assert resp.status_code in (401, 403)
