"""Magnetic Field Auto-Population Service.

Fetches magnetic field total intensity from NOAA WMM API and computes
expected range for location profiles.

Task A2: Magnetic field from NOAA World Magnetic Model.
"""
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# NOAA WMM API (free, public key from registration page)
NOAA_WMM_URL = "https://www.ngdc.noaa.gov/geomag-web/calculators/calculateIgrfwmm"
NOAA_API_KEY = "EAU2y"

# ±25 µT tolerance — indoor/urban environments have significant variance
# from metal structures, electronics, rebar in concrete
MAGNETIC_TOLERANCE_UT = 25.0


async def get_magnetic_field_intensity(
    latitude: float, longitude: float
) -> Optional[float]:
    """Fetch total magnetic field intensity from NOAA WMM API.

    Args:
        latitude: GPS latitude (decimal degrees).
        longitude: GPS longitude (decimal degrees).

    Returns:
        Total field intensity in µT (microtesla), or None on failure.
        NOAA returns nT, we convert to µT (divide by 1000).
    """
    now = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                NOAA_WMM_URL,
                params={
                    "lat1": round(latitude, 7),
                    "lon1": round(longitude, 7),
                    "model": "WMM",
                    "startYear": now.year,
                    "startMonth": now.month,
                    "startDay": now.day,
                    "endYear": now.year,
                    "endMonth": now.month,
                    "endDay": now.day,
                    "key": NOAA_API_KEY,
                    "resultFormat": "json",
                },
            )
            response.raise_for_status()
            data = response.json()


            # NOAA returns result array with field components
            # totalintensity is in nT, convert to µT
            result = data.get("result", [])
            if result and len(result) > 0:
                field_data = result[0]
                total_intensity_nt = field_data.get("totalintensity")
                if total_intensity_nt is not None:
                    total_intensity_ut = total_intensity_nt / 1000.0
                    logger.info(
                        f"Magnetic field for ({latitude}, {longitude}): "
                        f"{total_intensity_nt} nT = {total_intensity_ut:.2f} µT"
                    )
                    return round(total_intensity_ut, 2)

            logger.warning(
                f"No magnetic field data returned for ({latitude}, {longitude}). "
                f"Response: {data}"
            )
            return None

    except httpx.HTTPStatusError as e:
        logger.error(f"NOAA WMM API HTTP error: {e.response.status_code}")
        return None
    except httpx.RequestError as e:
        logger.error(f"NOAA WMM API request error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching magnetic field: {e}")
        return None


async def get_magnetic_field_range(
    latitude: float, longitude: float
) -> Optional[Tuple[float, float]]:
    """Get expected magnetic field range for a GPS location.

    Fetches total intensity from NOAA WMM and returns min/max
    with ±10 µT tolerance.

    Args:
        latitude: GPS latitude.
        longitude: GPS longitude.

    Returns:
        Tuple of (magnetic_min, magnetic_max) in µT, or None on failure.
    """
    intensity = await get_magnetic_field_intensity(latitude, longitude)
    if intensity is None:
        return None

    magnetic_min = round(intensity - MAGNETIC_TOLERANCE_UT, 2)
    magnetic_max = round(intensity + MAGNETIC_TOLERANCE_UT, 2)

    logger.info(
        f"Magnetic field range for ({latitude}, {longitude}): "
        f"intensity={intensity} µT, range=[{magnetic_min}, {magnetic_max}]"
    )

    return (magnetic_min, magnetic_max)
