"""
Tests for client management endpoints.
"""
import pytest
from httpx import AsyncClient
from app.models import Client


class TestClientProfile:
    """Test client profile endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_profile_success(self, client: AsyncClient, auth_headers: dict, test_client: Client):
        """Test getting current client profile."""
        response = await client.get(
            "/api/clients/me",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["company_name"] == "Test Company"
        assert data["phone_number"] == "+1234567890"
        assert data["subscription_tier"] == "free"
        assert data["subscription_status"] == "active"
    
    @pytest.mark.asyncio
    async def test_get_profile_no_auth(self, client: AsyncClient):
        """Test getting profile without authentication fails."""
        response = await client.get("/api/clients/me")
        
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_update_profile_company_name(self, client: AsyncClient, auth_headers: dict):
        """Test updating company name."""
        response = await client.patch(
            "/api/clients/me",
            headers=auth_headers,
            json={"company_name": "Updated Company"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["company_name"] == "Updated Company"
        assert data["email"] == "test@example.com"  # Unchanged
    
    @pytest.mark.asyncio
    async def test_update_profile_phone_number(self, client: AsyncClient, auth_headers: dict):
        """Test updating phone number."""
        response = await client.patch(
            "/api/clients/me",
            headers=auth_headers,
            json={"phone_number": "+1999999999"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["phone_number"] == "+1999999999"
    
    @pytest.mark.asyncio
    async def test_update_profile_multiple_fields(self, client: AsyncClient, auth_headers: dict):
        """Test updating multiple fields at once."""
        response = await client.patch(
            "/api/clients/me",
            headers=auth_headers,
            json={
                "company_name": "New Company Name",
                "phone_number": "+1888888888"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["company_name"] == "New Company Name"
        assert data["phone_number"] == "+1888888888"
    
    @pytest.mark.asyncio
    async def test_update_profile_invalid_phone(self, client: AsyncClient, auth_headers: dict):
        """Test updating with invalid phone number fails."""
        response = await client.patch(
            "/api/clients/me",
            headers=auth_headers,
            json={"phone_number": "invalid"}
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_update_profile_no_auth(self, client: AsyncClient):
        """Test updating profile without authentication fails."""
        response = await client.patch(
            "/api/clients/me",
            json={"company_name": "Hacker Company"}
        )
        
        assert response.status_code == 403


class TestClientSubscription:
    """Test client subscription endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_subscription_success(self, client: AsyncClient, auth_headers: dict):
        """Test getting current subscription."""
        response = await client.get(
            "/api/clients/me/subscription",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "free"
        assert data["status"] == "active"
        assert data["photos_quota"] == 50
        assert data["photos_used"] == 0
        assert "subscription_id" in data
        assert "current_period_start" in data
        assert "current_period_end" in data
    
    @pytest.mark.asyncio
    async def test_get_subscription_no_auth(self, client: AsyncClient):
        """Test getting subscription without authentication fails."""
        response = await client.get("/api/clients/me/subscription")
        
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_subscription_quota_tracking(self, client: AsyncClient, auth_headers: dict):
        """Test that subscription shows correct quota information."""
        response = await client.get(
            "/api/clients/me/subscription",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Free tier should have 50 photo quota
        assert data["photos_quota"] == 50
        # Initially no photos used
        assert data["photos_used"] == 0
        # Should have valid period dates
        assert data["current_period_start"] is not None
        assert data["current_period_end"] is not None


class TestEndToEndFlow:
    """Test complete end-to-end user flows."""
    
    @pytest.mark.asyncio
    async def test_complete_registration_and_profile_flow(self, client: AsyncClient):
        """Test complete flow: register -> login -> view profile -> update profile."""
        # Step 1: Register
        register_response = await client.post(
            "/api/auth/register",
            json={
                "email": "e2e@example.com",
                "password": "E2EPass123",
                "company_name": "E2E Company",
                "phone_number": "+1111111111"
            }
        )
        assert register_response.status_code == 201
        
        # Step 2: Login
        login_response = await client.post(
            "/api/auth/login",
            json={
                "email": "e2e@example.com",
                "password": "E2EPass123"
            }
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 3: View profile
        profile_response = await client.get(
            "/api/clients/me",
            headers=headers
        )
        assert profile_response.status_code == 200
        profile = profile_response.json()
        assert profile["email"] == "e2e@example.com"
        assert profile["company_name"] == "E2E Company"
        
        # Step 4: Update profile
        update_response = await client.patch(
            "/api/clients/me",
            headers=headers,
            json={"company_name": "Updated E2E Company"}
        )
        assert update_response.status_code == 200
        updated_profile = update_response.json()
        assert updated_profile["company_name"] == "Updated E2E Company"
        
        # Step 5: View subscription
        subscription_response = await client.get(
            "/api/clients/me/subscription",
            headers=headers
        )
        assert subscription_response.status_code == 200
        subscription = subscription_response.json()
        assert subscription["tier"] == "free"
        assert subscription["photos_quota"] == 50
