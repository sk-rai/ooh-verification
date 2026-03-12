"""
Tests for authentication endpoints.
"""
import pytest
from httpx import AsyncClient
from app.models import Client


class TestClientRegistration:
    """Test client registration endpoint."""
    
    @pytest.mark.asyncio
    async def test_register_client_success(self, client: AsyncClient):
        """Test successful client registration."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "newclient@example.com",
                "password": "SecurePass123",
                "company_name": "New Company",
                "phone_number": "+1234567890"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newclient@example.com"
        assert data["company_name"] == "New Company"
        assert data["subscription_tier"] == "free"
        assert data["subscription_status"] == "active"
        assert "client_id" in data
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_client: Client):
        """Test registration with duplicate email fails."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",  # Already exists
                "password": "SecurePass123",
                "company_name": "Another Company",
                "phone_number": "+1234567890"
            }
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: AsyncClient):
        """Test registration with weak password fails."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "newclient@example.com",
                "password": "weak",  # Too short, no uppercase, no digit
                "company_name": "New Company",
                "phone_number": "+1234567890"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email fails."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecurePass123",
                "company_name": "New Company",
                "phone_number": "+1234567890"
            }
        )
        
        assert response.status_code == 422  # Validation error


class TestClientLogin:
    """Test client login endpoint."""
    
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_client: Client):
        """Test successful client login."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPass123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_client: Client):
        """Test login with wrong password fails."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "WrongPassword123"
            }
        )
        
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with nonexistent user fails."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "TestPass123"
            }
        )
        
        assert response.status_code == 401


class TestVendorAuthentication:
    """Test vendor authentication endpoints."""
    
    @pytest.mark.asyncio
    async def test_vendor_request_otp_success(self, client: AsyncClient, test_vendor):
        """Test successful OTP request for vendor."""
        response = await client.post(
            "/api/auth/vendor/request-otp",
            json={
                "vendor_id": "TEST01",
                "phone_number": "+1987654321"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["expires_in"] == 600  # 10 minutes
    
    @pytest.mark.asyncio
    async def test_vendor_request_otp_wrong_phone(self, client: AsyncClient, test_vendor):
        """Test OTP request with wrong phone number fails."""
        response = await client.post(
            "/api/auth/vendor/request-otp",
            json={
                "vendor_id": "TEST01",
                "phone_number": "+9999999999"  # Wrong number
            }
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_vendor_request_otp_invalid_vendor(self, client: AsyncClient):
        """Test OTP request with invalid vendor ID fails."""
        response = await client.post(
            "/api/auth/vendor/request-otp",
            json={
                "vendor_id": "NOTFND",
                "phone_number": "+1987654321"
            }
        )
        
        assert response.status_code == 404


class TestAuthenticatedEndpoints:
    """Test authenticated endpoint access."""
    
    @pytest.mark.asyncio
    async def test_get_client_me_success(self, client: AsyncClient, auth_headers: dict, test_client: Client):
        """Test getting current client info with valid token."""
        response = await client.get(
            "/api/auth/me/client",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["company_name"] == "Test Company"
    
    @pytest.mark.asyncio
    async def test_get_client_me_no_token(self, client: AsyncClient):
        """Test getting current client info without token fails."""
        response = await client.get("/api/auth/me/client")
        
        assert response.status_code == 403  # No authorization header
    
    @pytest.mark.asyncio
    async def test_get_client_me_invalid_token(self, client: AsyncClient):
        """Test getting current client info with invalid token fails."""
        response = await client.get(
            "/api/auth/me/client",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401
