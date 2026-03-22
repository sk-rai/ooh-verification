"""Tests for elevation and magnetic field services (Tasks A1, A2)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.elevation_service import (
    compute_pressure_from_elevation, get_elevation, get_pressure_range,
    SEA_LEVEL_PRESSURE_HPA, PRESSURE_TOLERANCE_HPA,
)
from app.services.magnetic_field_service import (
    get_magnetic_field_intensity, get_magnetic_field_range,
    MAGNETIC_TOLERANCE_UT,
)


class TestComputePressure:
    """Test barometric formula."""

    def test_sea_level(self):
        p = compute_pressure_from_elevation(0)
        assert p == pytest.approx(SEA_LEVEL_PRESSURE_HPA, abs=0.1)

    def test_high_altitude(self):
        p = compute_pressure_from_elevation(5000)
        assert p < 600  # ~540 hPa at 5000m

    def test_negative_altitude(self):
        p = compute_pressure_from_elevation(-100)
        assert p > SEA_LEVEL_PRESSURE_HPA


class TestGetElevation:
    """Test Open-Meteo API call."""

    @patch("app.services.elevation_service.httpx.AsyncClient")
    async def test_get_elevation_success(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"elevation": [14.0]}
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client
        result = await get_elevation(19.076, 72.8777)
        assert result == 14.0

    @patch("app.services.elevation_service.httpx.AsyncClient")
    async def test_get_elevation_api_error(self, mock_client_cls):
        import httpx
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client
        result = await get_elevation(19.076, 72.8777)
        assert result is None


class TestGetPressureRange:
    """Test pressure range computation."""

    @patch("app.services.elevation_service.get_elevation", new_callable=AsyncMock, return_value=14.0)
    async def test_pressure_range_success(self, mock_elev):
        result = await get_pressure_range(19.076, 72.8777)
        assert result is not None
        p_min, p_max = result
        assert p_max - p_min == pytest.approx(2 * PRESSURE_TOLERANCE_HPA, abs=0.1)
        assert p_min < SEA_LEVEL_PRESSURE_HPA < p_max

    @patch("app.services.elevation_service.get_elevation", new_callable=AsyncMock, return_value=None)
    async def test_pressure_range_no_elevation(self, mock_elev):
        result = await get_pressure_range(0, 0)
        assert result is None


class TestGetMagneticFieldIntensity:
    """Test NOAA WMM API call."""

    @patch("app.services.magnetic_field_service.httpx.AsyncClient")
    async def test_magnetic_success(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [{"totalintensity": 43560.0}]}
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client
        result = await get_magnetic_field_intensity(19.076, 72.8777)
        assert result == pytest.approx(43.56, abs=0.01)

    @patch("app.services.magnetic_field_service.httpx.AsyncClient")
    async def test_magnetic_api_error(self, mock_client_cls):
        import httpx
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client
        result = await get_magnetic_field_intensity(19.076, 72.8777)
        assert result is None


class TestGetMagneticFieldRange:
    """Test magnetic field range computation."""

    @patch("app.services.magnetic_field_service.get_magnetic_field_intensity", new_callable=AsyncMock, return_value=43.56)
    async def test_magnetic_range_success(self, mock_intensity):
        result = await get_magnetic_field_range(19.076, 72.8777)
        assert result is not None
        m_min, m_max = result
        assert m_max - m_min == pytest.approx(2 * MAGNETIC_TOLERANCE_UT, abs=0.1)

    @patch("app.services.magnetic_field_service.get_magnetic_field_intensity", new_callable=AsyncMock, return_value=None)
    async def test_magnetic_range_no_data(self, mock_intensity):
        result = await get_magnetic_field_range(0, 0)
        assert result is None
