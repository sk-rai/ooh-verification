"""Tests for the unified /api/bulk/campaign-setup endpoint."""
import pytest
import io
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock


class TestBulkCampaignSetupTemplate:
    """Test GET /api/bulk/campaign-setup/template"""

    async def test_download_template(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/bulk/campaign-setup/template", headers=auth_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        content = resp.text
        # Verify header row
        lines = content.strip().split("\n")
        assert lines[0] == "campaign_name,campaign_type,start_date,end_date,location_address,vendor_name,vendor_phone,vendor_email"
        # Should have example rows
        assert len(lines) >= 2


class TestBulkCampaignSetup:
    """Test POST /api/bulk/campaign-setup"""

    def _make_csv(self, rows: list[str]) -> bytes:
        """Helper to create CSV bytes from rows."""
        header = "campaign_name,campaign_type,start_date,end_date,location_address,vendor_name,vendor_phone,vendor_email"
        content = header + "\n" + "\n".join(rows) + "\n"
        return content.encode("utf-8")

    async def test_single_row_creates_campaign_vendor_assignment(
        self, client: AsyncClient, auth_headers, test_subscription
    ):
        """A single valid row should create a campaign, vendor, and assignment."""
        csv_data = self._make_csv([
            '"Test Campaign Alpha","ooh","2026-08-01","2026-08-31","Connaught Place, Delhi","Test Vendor One","+919000000001","test1@example.com"'
        ])

        mock_geo = AsyncMock()
        mock_geo.latitude = 28.6315
        mock_geo.longitude = 77.2167
        mock_geo.formatted_address = "Connaught Place, New Delhi, India"

        with patch("app.api.bulk.get_geocoding_service") as mock_geo_svc:
            mock_geo_svc.return_value.geocode_address = AsyncMock(return_value=mock_geo)

            resp = await client.post(
                "/api/bulk/campaign-setup",
                files={"file": ("setup.csv", io.BytesIO(csv_data), "text/csv")},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rows"] == 1
        assert data["successful"] == 1
        assert data["failed"] == 0
        assert data["results"][0]["status"] == "success"
        assert data["results"][0]["data"]["campaign"] == "Test Campaign Alpha"
        assert data["results"][0]["data"]["vendor_phone"] == "+919000000001"

    async def test_multiple_vendors_same_campaign(
        self, client: AsyncClient, auth_headers, test_subscription
    ):
        """Multiple rows with same campaign should create one campaign, multiple vendors."""
        csv_data = self._make_csv([
            '"Multi Vendor Camp","ooh","2026-08-01","2026-08-31","MG Road, Bangalore","Vendor A","+919000000010",""',
            '"Multi Vendor Camp","ooh","2026-08-01","2026-08-31","MG Road, Bangalore","Vendor B","+919000000011",""',
            '"Multi Vendor Camp","ooh","2026-08-01","2026-08-31","MG Road, Bangalore","Vendor C","+919000000012",""',
        ])

        mock_geo = AsyncMock()
        mock_geo.latitude = 12.9716
        mock_geo.longitude = 77.5946
        mock_geo.formatted_address = "MG Road, Bangalore, India"

        with patch("app.api.bulk.get_geocoding_service") as mock_geo_svc:
            mock_geo_svc.return_value.geocode_address = AsyncMock(return_value=mock_geo)

            resp = await client.post(
                "/api/bulk/campaign-setup",
                files={"file": ("setup.csv", io.BytesIO(csv_data), "text/csv")},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rows"] == 3
        assert data["successful"] == 3
        assert data["failed"] == 0
        # All should reference same campaign
        campaign_codes = set(r["data"]["campaign_code"] for r in data["results"])
        assert len(campaign_codes) == 1  # only 1 campaign created

    async def test_same_vendor_multiple_campaigns(
        self, client: AsyncClient, auth_headers, test_subscription
    ):
        """Same vendor phone appearing in different campaigns should create vendor once."""
        csv_data = self._make_csv([
            '"Camp One","ooh","2026-08-01","2026-08-31","Delhi","Shared Vendor","+919000000020",""',
            '"Camp Two","construction","2026-09-01","2026-09-30","Mumbai","Shared Vendor","+919000000020",""',
        ])

        mock_geo = AsyncMock()
        mock_geo.latitude = 28.0
        mock_geo.longitude = 77.0
        mock_geo.formatted_address = "Some Address"

        with patch("app.api.bulk.get_geocoding_service") as mock_geo_svc:
            mock_geo_svc.return_value.geocode_address = AsyncMock(return_value=mock_geo)

            resp = await client.post(
                "/api/bulk/campaign-setup",
                files={"file": ("setup.csv", io.BytesIO(csv_data), "text/csv")},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["successful"] == 2
        # Same vendor_id for both rows
        vendor_ids = set(r["data"]["vendor_id"] for r in data["results"])
        assert len(vendor_ids) == 1

    async def test_missing_required_field(
        self, client: AsyncClient, auth_headers, test_subscription
    ):
        """Row missing required field should fail gracefully."""
        csv_data = self._make_csv([
            '"Valid Camp","ooh","2026-08-01","2026-08-31","Delhi","Good Vendor","+919000000030",""',
            '"","ooh","2026-08-01","2026-08-31","Delhi","Bad Row","+919000000031",""',  # missing campaign_name
        ])

        with patch("app.api.bulk.get_geocoding_service") as mock_geo_svc:
            mock_geo = AsyncMock()
            mock_geo.latitude = 28.0
            mock_geo.longitude = 77.0
            mock_geo.formatted_address = "Delhi"
            mock_geo_svc.return_value.geocode_address = AsyncMock(return_value=mock_geo)

            resp = await client.post(
                "/api/bulk/campaign-setup",
                files={"file": ("setup.csv", io.BytesIO(csv_data), "text/csv")},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["successful"] == 1
        assert data["failed"] == 1
        # Check error message
        error_row = [r for r in data["results"] if r["status"] == "error"][0]
        assert "campaign_name" in error_row["error"].lower()

    async def test_invalid_phone_format(
        self, client: AsyncClient, auth_headers, test_subscription
    ):
        """Invalid phone number should fail."""
        csv_data = self._make_csv([
            '"Phone Camp","ooh","2026-08-01","2026-08-31","Delhi","Bad Phone","1234567",""',  # no +
        ])

        with patch("app.api.bulk.get_geocoding_service") as mock_geo_svc:
            mock_geo_svc.return_value.geocode_address = AsyncMock(return_value=None)

            resp = await client.post(
                "/api/bulk/campaign-setup",
                files={"file": ("setup.csv", io.BytesIO(csv_data), "text/csv")},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["failed"] == 1
        assert "E.164" in data["results"][0]["error"]

    async def test_invalid_campaign_type(
        self, client: AsyncClient, auth_headers, test_subscription
    ):
        """Invalid campaign type should fail."""
        csv_data = self._make_csv([
            '"Bad Type Camp","invalid_type","2026-08-01","2026-08-31","Delhi","Vendor X","+919000000040",""',
        ])

        resp = await client.post(
            "/api/bulk/campaign-setup",
            files={"file": ("setup.csv", io.BytesIO(csv_data), "text/csv")},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["failed"] == 1
        assert "campaign_type" in data["results"][0]["error"].lower()

    async def test_no_location_still_succeeds(
        self, client: AsyncClient, auth_headers, test_subscription
    ):
        """Row without location_address should still create campaign+vendor+assignment."""
        csv_data = self._make_csv([
            '"No Location Camp","ooh","2026-08-01","2026-08-31","","Vendor NoLoc","+919000000050",""',
        ])

        resp = await client.post(
            "/api/bulk/campaign-setup",
            files={"file": ("setup.csv", io.BytesIO(csv_data), "text/csv")},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["successful"] == 1
        assert data["results"][0]["data"]["location"] == "N/A"

    async def test_geocoding_failure_still_succeeds(
        self, client: AsyncClient, auth_headers, test_subscription
    ):
        """If geocoding fails, row should still succeed (no location profile created)."""
        csv_data = self._make_csv([
            '"Geo Fail Camp","ooh","2026-08-01","2026-08-31","Nonexistent Place XYZ","Vendor GeoFail","+919000000060",""',
        ])

        with patch("app.api.bulk.get_geocoding_service") as mock_geo_svc:
            mock_geo_svc.return_value.geocode_address = AsyncMock(side_effect=Exception("Geocoding failed"))

            resp = await client.post(
                "/api/bulk/campaign-setup",
                files={"file": ("setup.csv", io.BytesIO(csv_data), "text/csv")},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["successful"] == 1  # Still succeeds, just no location profile

    async def test_empty_file_rejected(self, client: AsyncClient, auth_headers):
        """Empty CSV should be rejected."""
        csv_data = b"campaign_name,campaign_type,start_date,end_date,location_address,vendor_name,vendor_phone,vendor_email\n"

        resp = await client.post(
            "/api/bulk/campaign-setup",
            files={"file": ("empty.csv", io.BytesIO(csv_data), "text/csv")},
            headers=auth_headers,
        )

        # Should return 200 with 0 rows or 400
        data = resp.json()
        assert data.get("total_rows", 0) == 0 or resp.status_code == 400
