"""
Integration tests for vendor management endpoints.

**Validates: Requirements 1.1, 1.2, 1.3**
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Vendor, Client
from app.models.vendor import VendorStatus


class TestVendorCreation:
    """
    Test vendor creation endpoint.
    
    Requirements:
        - Req 1.1: Vendor creation by clients
        - Req 1.2: Vendor ID generation
        - Req 1.3: SMS delivery with vendor ID
    """
    
    @pytest.mark.asyncio
    async def test_create_vendor_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession
    ):
        """Test successful vendor creation."""
        vendor_data = {
            "name": "John Doe",
            "phone_number": "+1234567890",
            "email": "john@example.com"
        }
        
        response = await client.post(
            "/api/vendors",
            json=vendor_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify response structure
        assert "vendor_id" in data
        assert len(data["vendor_id"]) == 6
        assert data["name"] == vendor_data["name"]
        assert data["phone_number"] == vendor_data["phone_number"]
        assert data["email"] == vendor_data["email"]
        assert data["status"] == "active"
        
        # Verify vendor was created in database
        result = await db_session.execute(
            select(Vendor).where(Vendor.vendor_id == data["vendor_id"])
        )
        vendor = result.scalar_one_or_none()
        assert vendor is not None
        assert vendor.name == vendor_data["name"]
    
    @pytest.mark.asyncio
    async def test_create_vendor_without_email(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test vendor creation without optional email."""
        vendor_data = {
            "name": "Jane Smith",
            "phone_number": "+1987654321"
        }
        
        response = await client.post(
            "/api/vendors",
            json=vendor_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] is None
    
    @pytest.mark.asyncio
    async def test_create_vendor_invalid_phone(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test vendor creation with invalid phone number."""
        vendor_data = {
            "name": "Invalid Phone",
            "phone_number": "invalid"
        }
        
        response = await client.post(
            "/api/vendors",
            json=vendor_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_create_vendor_unauthorized(
        self,
        client: AsyncClient
    ):
        """Test vendor creation without authentication."""
        vendor_data = {
            "name": "Unauthorized",
            "phone_number": "+1234567890"
        }
        
        response = await client.post(
            "/api/vendors",
            json=vendor_data
        )
        
        assert response.status_code == 403  # HTTPBearer returns 403 when no credentials provided


class TestVendorListing:
    """
    Test vendor listing endpoint.
    
    Requirements:
        - Req 1.1: Vendor listing for clients
        - Authorization: Clients can only see their own vendors
    """
    
    @pytest.mark.asyncio
    async def test_list_vendors_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_vendor: Vendor
    ):
        """Test successful vendor listing."""
        response = await client.get(
            "/api/vendors",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "vendors" in data
        assert "total" in data
        assert data["total"] >= 1
        assert len(data["vendors"]) >= 1
        
        # Verify vendor structure
        vendor = data["vendors"][0]
        assert "vendor_id" in vendor
        assert "name" in vendor
        assert "status" in vendor
    
    @pytest.mark.asyncio
    async def test_list_vendors_with_status_filter(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_vendor: Vendor
    ):
        """Test vendor listing with status filter."""
        response = await client.get(
            "/api/vendors?status_filter=active",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned vendors should be active
        for vendor in data["vendors"]:
            assert vendor["status"] == "active"
    
    @pytest.mark.asyncio
    async def test_list_vendors_with_pagination(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_vendor: Vendor
    ):
        """Test vendor listing with pagination."""
        response = await client.get(
            "/api/vendors?skip=0&limit=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["vendors"]) <= 10
    
    @pytest.mark.asyncio
    async def test_list_vendors_unauthorized(
        self,
        client: AsyncClient
    ):
        """Test vendor listing without authentication."""
        response = await client.get("/api/vendors")
        assert response.status_code == 403  # HTTPBearer returns 403 when no credentials provided
    
    @pytest.mark.asyncio
    async def test_list_vendors_invalid_status(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test vendor listing with invalid status filter."""
        response = await client.get(
            "/api/vendors?status_filter=invalid",
            headers=auth_headers
        )
        
        assert response.status_code == 400


class TestVendorUpdate:
    """
    Test vendor update endpoint.
    
    Requirements:
        - Req 1.2: Vendor information updates
        - Authorization: Clients can only update their own vendors
    """
    
    @pytest.mark.asyncio
    async def test_update_vendor_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_vendor: Vendor,
        db_session: AsyncSession
    ):
        """Test successful vendor update."""
        update_data = {
            "name": "Updated Name",
            "email": "updated@example.com"
        }
        
        response = await client.patch(
            f"/api/vendors/{test_vendor.vendor_id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == update_data["name"]
        assert data["email"] == update_data["email"]
        
        # Verify update in database
        await db_session.refresh(test_vendor)
        assert test_vendor.name == update_data["name"]
        assert test_vendor.email == update_data["email"]
    
    @pytest.mark.asyncio
    async def test_update_vendor_partial(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_vendor: Vendor
    ):
        """Test partial vendor update (only one field)."""
        update_data = {
            "name": "Only Name Updated"
        }
        
        response = await client.patch(
            f"/api/vendors/{test_vendor.vendor_id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        # Other fields should remain unchanged
        assert data["phone_number"] == test_vendor.phone_number
    
    @pytest.mark.asyncio
    async def test_update_vendor_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test updating non-existent vendor."""
        update_data = {"name": "Not Found"}
        
        response = await client.patch(
            "/api/vendors/NOTFND",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_update_vendor_unauthorized(
        self,
        client: AsyncClient,
        test_vendor: Vendor
    ):
        """Test vendor update without authentication."""
        update_data = {"name": "Unauthorized"}
        
        response = await client.patch(
            f"/api/vendors/{test_vendor.vendor_id}",
            json=update_data
        )
        
        assert response.status_code == 403  # HTTPBearer returns 403 when no credentials provided


class TestVendorDeactivation:
    """
    Test vendor deactivation endpoint.
    
    Requirements:
        - Req 1.3: Vendor deactivation
        - Authorization: Clients can only deactivate their own vendors
    """
    
    @pytest.mark.asyncio
    async def test_deactivate_vendor_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_vendor: Vendor,
        db_session: AsyncSession
    ):
        """Test successful vendor deactivation."""
        response = await client.patch(
            f"/api/vendors/{test_vendor.vendor_id}/deactivate",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "inactive"
        
        # Verify deactivation in database
        await db_session.refresh(test_vendor)
        assert test_vendor.status == VendorStatus.INACTIVE
    
    @pytest.mark.asyncio
    async def test_deactivate_vendor_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test deactivating non-existent vendor."""
        response = await client.patch(
            "/api/vendors/NOTFND/deactivate",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_deactivate_vendor_unauthorized(
        self,
        client: AsyncClient,
        test_vendor: Vendor
    ):
        """Test vendor deactivation without authentication."""
        response = await client.patch(
            f"/api/vendors/{test_vendor.vendor_id}/deactivate"
        )
        
        assert response.status_code == 403  # HTTPBearer returns 403 when no credentials provided


class TestVendorAuthorization:
    """
    Test authorization rules for vendor endpoints.
    
    Requirements:
        - Authorization: Clients can only access their own vendors
    """
    
    @pytest.mark.asyncio
    async def test_client_cannot_see_other_clients_vendors(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_client: Client
    ):
        """Test that clients can only see their own vendors."""
        # Create another client
        from app.models.client import SubscriptionTier, SubscriptionStatus
        from app.core.security import hash_password
        import uuid
        from datetime import datetime, timedelta
        
        other_client = Client(
            client_id=uuid.uuid4(),
            email='other@example.com',
            password_hash=hash_password('OtherPass123'),
            company_name='Other Company',
            phone_number='+1111111111',
            subscription_tier=SubscriptionTier.FREE,
            subscription_status=SubscriptionStatus.ACTIVE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(other_client)
        
        # Create vendor for other client
        other_vendor = Vendor(
            vendor_id='OTHER1',
            created_by_client_id=other_client.client_id,
            name='Other Vendor',
            phone_number='+2222222222',
            status=VendorStatus.ACTIVE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(other_vendor)
        await db_session.commit()
        
        # Login as test_client
        login_response = await client.post(
            '/api/auth/login',
            json={'email': 'test@example.com', 'password': 'TestPass123'}
        )
        token = login_response.json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        
        # Try to list vendors - should not see other client's vendor
        response = await client.get('/api/vendors', headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        vendor_ids = [v['vendor_id'] for v in data['vendors']]
        assert 'OTHER1' not in vendor_ids
