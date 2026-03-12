"""
Integration tests for campaign management endpoints.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 7.1, 7.2, 7.3, 7.4, 12.1**
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from uuid import uuid4

from app.models import Campaign, LocationProfile, CampaignVendorAssignment, Vendor
from app.models.campaign import CampaignStatus, CampaignType


class TestCampaignCreation:
    """
    Test campaign creation endpoint.

    Requirements:
        - Req 1.1: Campaign creation
        - Req 1.2: Campaign code validation
        - Req 1.4: Campaign expiration dates
        - Req 12.1: Campaign code format
    """

    @pytest.mark.asyncio
    async def test_create_campaign_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession
    ):
        """Test successful campaign creation without location profile."""
        campaign_data = {
            "name": "Test Campaign",
            "campaign_type": "ooh",
            "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=30)).isoformat()
        }

        response = await client.post(
            "/api/campaigns",
            json=campaign_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()

        # Verify response structure
        assert "campaign_id" in data
        assert "campaign_code" in data
        assert data["name"] == campaign_data["name"]
        assert data["campaign_type"] == campaign_data["campaign_type"]
        assert data["status"] == "active"

        # Verify campaign code format (PREFIX-YEAR-XXXX)
        code_parts = data["campaign_code"].split("-")
        assert len(code_parts) == 3
        assert len(code_parts[0]) >= 2  # Prefix
        assert len(code_parts[1]) == 4  # Year
        assert len(code_parts[2]) == 4  # Random suffix

        # Verify in database
        result = await db_session.execute(
            select(Campaign).where(Campaign.campaign_code == data["campaign_code"])
        )
        db_campaign = result.scalar_one_or_none()
        assert db_campaign is not None
        assert db_campaign.name == campaign_data["name"]

    @pytest.mark.asyncio
    async def test_create_campaign_with_location_profile(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession
    ):
        """Test campaign creation with location profile."""
        campaign_data = {
            "name": "Times Square Campaign",
            "campaign_type": "ooh",
            "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "location_profile": {
                "expected_latitude": 40.7580000,
                "expected_longitude": -73.9855000,
                "tolerance_meters": 50.0,
                "expected_wifi_bssids": ["00:11:22:33:44:55"],
                "expected_cell_tower_ids": [12345],
                "expected_pressure_min": 1010.0,
                "expected_pressure_max": 1020.0,
                "expected_light_min": 100.0,
                "expected_light_max": 500.0
            }
        }

        response = await client.post(
            "/api/campaigns",
            json=campaign_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()

        # Verify location profile in response
        assert data["location_profile"] is not None
        profile = data["location_profile"]
        assert profile["expected_latitude"] == 40.7580000
        assert profile["expected_longitude"] == -73.9855000
        assert profile["tolerance_meters"] == 50.0
        assert profile["expected_wifi_bssids"] == ["00:11:22:33:44:55"]
        assert profile["expected_cell_tower_ids"] == [12345]

        # Verify in database
        result = await db_session.execute(
            select(LocationProfile).where(
                LocationProfile.campaign_id == data["campaign_id"]
            )
        )
        db_profile = result.scalar_one_or_none()
        assert db_profile is not None
        assert abs(db_profile.expected_latitude - 40.7580000) < 0.0001
        assert abs(db_profile.expected_longitude - (-73.9855000)) < 0.0001

    @pytest.mark.asyncio
    async def test_create_campaign_invalid_dates(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test campaign creation with invalid dates (end before start)."""
        campaign_data = {
            "name": "Invalid Campaign",
            "campaign_type": "ooh",
            "start_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=1)).isoformat()
        }

        response = await client.post(
            "/api/campaigns",
            json=campaign_data,
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_campaign_invalid_type(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test campaign creation with invalid campaign type."""
        campaign_data = {
            "name": "Invalid Type Campaign",
            "campaign_type": "invalid_type",
            "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=30)).isoformat()
        }

        response = await client.post(
            "/api/campaigns",
            json=campaign_data,
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error


class TestCampaignListing:
    """
    Test campaign listing endpoint.

    Requirements:
        - Req 1.2: Campaign listing
        - Authorization: Clients can only see their own campaigns
    """

    @pytest.mark.asyncio
    async def test_list_campaigns_empty(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test listing campaigns when none exist."""
        response = await client.get(
            "/api/campaigns",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "campaigns" in data
        assert "total" in data
        assert isinstance(data["campaigns"], list)

    @pytest.mark.asyncio
    async def test_list_campaigns_with_data(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_client
    ):
        """Test listing campaigns with existing data."""
        # Create test campaigns
        campaign1 = Campaign(
            campaign_code="TEST-2026-AAA1",
            name="Campaign 1",
            campaign_type=CampaignType.OOH_ADVERTISING,
            client_id=test_client.client_id,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            status=CampaignStatus.ACTIVE
        )
        campaign2 = Campaign(
            campaign_code="TEST-2026-BBB2",
            name="Campaign 2",
            campaign_type=CampaignType.CONSTRUCTION,
            client_id=test_client.client_id,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=60),
            status=CampaignStatus.COMPLETED
        )

        db_session.add(campaign1)
        db_session.add(campaign2)
        await db_session.commit()

        response = await client.get(
            "/api/campaigns",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["campaigns"]) >= 2

    @pytest.mark.asyncio
    async def test_list_campaigns_filter_by_status(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_client
    ):
        """Test filtering campaigns by status."""
        # Create campaigns with different statuses
        active_campaign = Campaign(
            campaign_code="TEST-2026-ACT1",
            name="Active Campaign",
            campaign_type=CampaignType.OOH_ADVERTISING,
            client_id=test_client.client_id,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            status=CampaignStatus.ACTIVE
        )
        completed_campaign = Campaign(
            campaign_code="TEST-2026-CMP1",
            name="Completed Campaign",
            campaign_type=CampaignType.OOH_ADVERTISING,
            client_id=test_client.client_id,
            start_date=datetime.utcnow() - timedelta(days=60),
            end_date=datetime.utcnow() - timedelta(days=30),
            status=CampaignStatus.COMPLETED
        )

        db_session.add(active_campaign)
        db_session.add(completed_campaign)
        await db_session.commit()

        # Filter by active status
        response = await client.get(
            "/api/campaigns?status_filter=active",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        for campaign in data["campaigns"]:
            assert campaign["status"] == "active"


class TestCampaignRetrieval:
    """
    Test campaign retrieval endpoint.

    Requirements:
        - Req 1.3: Campaign details retrieval
        - Authorization: Clients can only access their own campaigns
    """

    @pytest.mark.asyncio
    async def test_get_campaign_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_client
    ):
        """Test successful campaign retrieval."""
        # Create test campaign
        campaign = Campaign(
            campaign_code="TEST-2026-GET1",
            name="Get Test Campaign",
            campaign_type=CampaignType.OOH_ADVERTISING,
            client_id=test_client.client_id,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            status=CampaignStatus.ACTIVE
        )
        db_session.add(campaign)
        await db_session.commit()
        await db_session.refresh(campaign)

        response = await client.get(
            f"/api/campaigns/{campaign.campaign_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["campaign_id"] == str(campaign.campaign_id)
        assert data["name"] == campaign.name

    @pytest.mark.asyncio
    async def test_get_campaign_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test retrieving non-existent campaign."""
        fake_id = uuid4()
        response = await client.get(
            f"/api/campaigns/{fake_id}",
            headers=auth_headers
        )

        assert response.status_code == 404


class TestCampaignUpdate:
    """
    Test campaign update endpoint.

    Requirements:
        - Req 1.4: Campaign updates
        - Authorization: Clients can only update their own campaigns
    """

    @pytest.mark.asyncio
    async def test_update_campaign_name(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_client
    ):
        """Test updating campaign name."""
        # Create test campaign
        campaign = Campaign(
            campaign_code="TEST-2026-UPD1",
            name="Original Name",
            campaign_type=CampaignType.OOH_ADVERTISING,
            client_id=test_client.client_id,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            status=CampaignStatus.ACTIVE
        )
        db_session.add(campaign)
        await db_session.commit()
        await db_session.refresh(campaign)

        update_data = {"name": "Updated Name"}

        response = await client.patch(
            f"/api/campaigns/{campaign.campaign_id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

        # Verify in database
        await db_session.refresh(campaign)
        assert campaign.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_campaign_status(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_client
    ):
        """Test updating campaign status."""
        campaign = Campaign(
            campaign_code="TEST-2026-STA1",
            name="Status Test",
            campaign_type=CampaignType.OOH_ADVERTISING,
            client_id=test_client.client_id,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            status=CampaignStatus.ACTIVE
        )
        db_session.add(campaign)
        await db_session.commit()
        await db_session.refresh(campaign)

        update_data = {"status": "completed"}

        response = await client.patch(
            f"/api/campaigns/{campaign.campaign_id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"


class TestVendorAssignment:
    """
    Test vendor assignment endpoints.

    Requirements:
        - Req 1.1: Vendor assignment to campaigns
        - Req 1.3: SMS notifications to assigned vendors
    """

    @pytest.mark.asyncio
    async def test_assign_vendors_to_campaign(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_client
    ):
        """Test assigning vendors to a campaign."""
        # Create test campaign
        campaign = Campaign(
            campaign_code="TEST-2026-VND1",
            name="Vendor Assignment Test",
            campaign_type=CampaignType.OOH_ADVERTISING,
            client_id=test_client.client_id,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            status=CampaignStatus.ACTIVE
        )
        db_session.add(campaign)

        # Create test vendors
        vendor1 = Vendor(
            vendor_id="VND001",
            name="Vendor One",
            phone_number="+1234567890",
            created_by_client_id=test_client.client_id
        )
        vendor2 = Vendor(
            vendor_id="VND002",
            name="Vendor Two",
            phone_number="+1234567891",
            created_by_client_id=test_client.client_id
        )
        db_session.add(vendor1)
        db_session.add(vendor2)
        await db_session.commit()
        await db_session.refresh(campaign)

        # Assign vendors
        assignment_data = {
            "vendor_ids": ["VND001", "VND002"]
        }

        response = await client.post(
            f"/api/campaigns/{campaign.campaign_id}/vendors",
            json=assignment_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data) == 2

        # Verify in database
        result = await db_session.execute(
            select(CampaignVendorAssignment).where(
                CampaignVendorAssignment.campaign_id == campaign.campaign_id
            )
        )
        assignments = result.scalars().all()
        assert len(assignments) == 2

    @pytest.mark.asyncio
    async def test_assign_nonexistent_vendor(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_client
    ):
        """Test assigning non-existent vendor to campaign."""
        campaign = Campaign(
            campaign_code="TEST-2026-NVN1",
            name="Non-existent Vendor Test",
            campaign_type=CampaignType.OOH_ADVERTISING,
            client_id=test_client.client_id,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            status=CampaignStatus.ACTIVE
        )
        db_session.add(campaign)
        await db_session.commit()
        await db_session.refresh(campaign)

        assignment_data = {
            "vendor_ids": ["FAKE99"]
        }

        response = await client.post(
            f"/api/campaigns/{campaign.campaign_id}/vendors",
            json=assignment_data,
            headers=auth_headers
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_remove_vendor_from_campaign(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_client
    ):
        """Test removing vendor assignment from campaign."""
        # Create test campaign and vendor
        campaign = Campaign(
            campaign_code="TEST-2026-RMV1",
            name="Remove Vendor Test",
            campaign_type=CampaignType.OOH_ADVERTISING,
            client_id=test_client.client_id,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            status=CampaignStatus.ACTIVE
        )
        vendor = Vendor(
            vendor_id="RMV001",
            name="Remove Test Vendor",
            phone_number="+1234567890",
            created_by_client_id=test_client.client_id
        )
        db_session.add(campaign)
        db_session.add(vendor)
        await db_session.commit()
        await db_session.refresh(campaign)

        # Create assignment
        assignment = CampaignVendorAssignment(
            campaign_id=campaign.campaign_id,
            vendor_id=vendor.vendor_id
        )
        db_session.add(assignment)
        await db_session.commit()

        # Remove assignment
        response = await client.delete(
            f"/api/campaigns/{campaign.campaign_id}/vendors/{vendor.vendor_id}",
            headers=auth_headers
        )

        assert response.status_code == 204

        # Verify removed from database
        result = await db_session.execute(
            select(CampaignVendorAssignment).where(
                CampaignVendorAssignment.campaign_id == campaign.campaign_id,
                CampaignVendorAssignment.vendor_id == vendor.vendor_id
            )
        )
        removed_assignment = result.scalar_one_or_none()
        assert removed_assignment is None
