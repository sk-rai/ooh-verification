"""
Authentication API Tests
Tests all authentication endpoints with comprehensive coverage.
"""
import pytest
from httpx import AsyncClient


class TestClientRegistration:
    """Test client registration endpoint."""
    
    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient, test_tenant):
        """Test successful client registration."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "newclient@example.com",
                "password": "SecurePass123!",
                "company_name": "New Company",
                "phone_number": "+1987654321"
            },
            headers={"X-Tenant-ID": str(test_tenant.tenant_id)}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newclient@example.com"
        assert data["company_name"] == "New Company"
        assert "client_id" in data
        assert "password_hash" not in data  # Password should not be returned
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_tenant, test_client_user):
        """Test registration with duplicate email fails."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": test_client_user.email,
                "password": "SecurePass123!",
                "company_name": "Duplicate Company",
                "phone_number": "+1987654321"
            },
            headers={"X-Tenant-ID": str(test_tenant.tenant_id)}
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient, test_tenant):
        """Test registration with invalid email format."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "invalid-email",
                "password": "SecurePass123!",
                "company_name": "Test Company",
                "phone_number": "+1987654321"
            },
            headers={"X-Tenant-ID": str(test_tenant.tenant_id)}
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: AsyncClient, test_tenant):
        """Test registration with weak password."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "weak",
                "company_name": "Test Company",
                "phone_number": "+1987654321"
            },
            headers={"X-Tenant-ID": str(test_tenant.tenant_id)}
        )
        
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client: AsyncClient, test_tenant):
        """Test registration with missing required fields."""
        response = await client.post(
            "/api/auth/register",
            json={"email": "test@example.com"},
            headers={"X-Tenant-ID": str(test_tenant.tenant_id)}
        )
        
        assert response.status_code == 422


class TestClientLogin:
    """Test client login endpoint."""
    
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_tenant, test_client_user):
        """Test successful login."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": test_client_user.email,
                "password": "Test123!@#"
            },
            headers={"X-Tenant-ID": str(test_tenant.tenant_id)}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_login_invalid_email(self, client: AsyncClient, test_tenant):
        """Test login with non-existent email."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "Test123!@#"
            },
            headers={"X-Tenant-ID": str(test_tenant.tenant_id)}
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client: AsyncClient, test_tenant, test_client_user):
        """Test login with incorrect password."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": test_client_user.email,
                "password": "WrongPassword123!"
            },
            headers={"X-Tenant-ID": str(test_tenant.tenant_id)}
        )
        
        assert response.status_code == 401


class TestGetCurrentUser:
    """Test get current user endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_success(self, client: AsyncClient, auth_headers):
        """Test getting current user with valid token."""
        response = await client.get(
            "/api/auth/me/client",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert "client_id" in data
    
    @pytest.mark.asyncio
    async def test_get_current_user_no_token(self, client: AsyncClient, test_tenant):
        """Test getting current user without token."""
        response = await client.get(
            "/api/auth/me/client",
            headers={"X-Tenant-ID": str(test_tenant.tenant_id)}
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient, test_tenant):
        """Test getting current user with invalid token."""
        response = await client.get(
            "/api/auth/me/client",
            headers={
                "Authorization": "Bearer invalid_token",
                "X-Tenant-ID": str(test_tenant.tenant_id)
            }
        )
        
        assert response.status_code == 401
