"""Comprehensive vendor endpoint tests."""
import pytest
from httpx import AsyncClient


class TestCreateVendor:
    """Test POST /api/vendors"""

    async def test_create_vendor_success(self, client: AsyncClient, auth_headers, test_subscription):
        resp = await client.post("/api/vendors", json={
            "name": "Field Worker 1",
            "phone_number": "+919999888877",
            "email": "worker1@example.com",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Field Worker 1"
        assert len(data["vendor_id"]) == 6
        assert data["status"] == "active"

    async def test_create_vendor_no_auth(self, client: AsyncClient):
        resp = await client.post("/api/vendors", json={
            "name": "No Auth Vendor",
            "phone_number": "+919999888866",
        })
        assert resp.status_code in (401, 403)


class TestListVendors:
    """Test GET /api/vendors"""

    async def test_list_vendors(self, client: AsyncClient, auth_headers, test_vendor, test_subscription):
        resp = await client.get("/api/vendors", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "vendors" in data
        assert "total" in data
        assert data["total"] >= 1

    async def test_list_vendors_filter_active(self, client: AsyncClient, auth_headers, test_vendor, test_subscription):
        resp = await client.get("/api/vendors?status_filter=active", headers=auth_headers)
        assert resp.status_code == 200
        for v in resp.json()["vendors"]:
            assert v["status"] == "active"

    async def test_list_vendors_pagination(self, client: AsyncClient, auth_headers, test_vendor, test_subscription):
        resp = await client.get("/api/vendors?skip=0&limit=1", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["vendors"]) <= 1


class TestUpdateVendor:
    """Test PATCH /api/vendors/{vendor_id}"""

    async def test_update_vendor_name(self, client: AsyncClient, auth_headers, test_vendor, test_subscription):
        resp = await client.patch(f"/api/vendors/{test_vendor.vendor_id}", json={
            "name": "Updated Vendor Name",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Vendor Name"

    async def test_update_nonexistent_vendor(self, client: AsyncClient, auth_headers, test_subscription):
        resp = await client.patch("/api/vendors/ZZZZZZ", json={"name": "Ghost"}, headers=auth_headers)
        assert resp.status_code == 404


class TestDeactivateVendor:
    """Test PATCH /api/vendors/{vendor_id}/deactivate"""

    async def test_deactivate_vendor(self, client: AsyncClient, auth_headers, test_vendor, test_subscription):
        resp = await client.patch(f"/api/vendors/{test_vendor.vendor_id}/deactivate", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"

    async def test_deactivate_nonexistent(self, client: AsyncClient, auth_headers, test_subscription):
        resp = await client.patch("/api/vendors/ZZZZZZ/deactivate", headers=auth_headers)
        assert resp.status_code == 404
