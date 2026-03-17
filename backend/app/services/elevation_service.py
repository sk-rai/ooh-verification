"""Elevation and Pressure Auto-Population Service.

Fetches elevation data from Open-Meteo API and computes expected
barometric pressure range for location profiles.

Task A1: Pressure range auto-population from elevation.
"""
import logging
import httpx
import math
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Open-Meteo elevation API (free, no key required)
OPEN_METEO_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"

# Barometric formula constants
SEA_LEVEL_PRESSURE_HPA = 1013.25
PRESSURE_TOLERANCE_HPA = 15.0  # ±15 hPa tolerance


def compute_pressure_from_elevation(altitude_meters: float) -> float:
    """Compute expected barometric pressure using the barometric formula.

    P = 1013.25 * (1 - 0.0000225577 * altitude) ^ 5.25588

    Args:
        altitude_meters: Elevation above sea level in meters.

    Returns:
        Expected pressure in hPa (hectopascals).
    """
    pressure = SEA_LEVEL_PRESSURE_HPA * (
        (1 - 0.0000225577 * altitude_meters) ** 5.25588
    )
    return round(pressure, 2)


async def get_elevation(latitude: float, longitude: float) -> Optional[float]:
    """Fetch elevation from Open-Meteo API.

    Args:
        latitude: GPS latitude (decimal degrees).
        longitude: GPS longitude (decimal degrees).

    Returns:
        Elevation in meters, or None if the API call fails.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                OPEN_METEO_ELEVATION_URL,
                params={
                    "latitude": round(latitude, 7),
                    "longitude": round(longitude, 7),
                },
            )
            response.raise_for_status()
            data = response.json()

            elevations = data.get("elevation")
            if elevations and len(elevations) > 0:
                elevation = elevations[0]
                logger.info(
                    f"Elevation for ({latitude}, {longitude}): {elevation}m"
                )
                return float(elevation)

            logger.warning(f"No elevation data returned for ({latitude}, {longitude})")
            return None

    except httpx.HTTPStatusError as e:
        logger.error(f"Open-Meteo API HTTP error: {e.response.status_code}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Open-Meteo API request error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching elevation: {e}")
        return None



async def get_pressure_range(
    latitude: float, longitude: float
) -> Optional[Tuple[float, float]]:
    """Get expected pressure range for a GPS location.

    Fetches elevation from Open-Meteo, computes pressure via barometric
    formula, and returns min/max with ±15 hPa tolerance.

    Args:
        latitude: GPS latitude.
        longitude: GPS longitude.

    Returns:
        Tuple of (pressure_min, pressure_max) in hPa, or None on failure.
    """
    elevation = await get_elevation(latitude, longitude)
    if elevation is None:
        return None

    expected_pressure = compute_pressure_from_elevation(elevation)
    pressure_min = round(expected_pressure - PRESSURE_TOLERANCE_HPA, 2)
    pressure_max = round(expected_pressure + PRESSURE_TOLERANCE_HPA, 2)

    logger.info(
        f"Pressure range for ({latitude}, {longitude}): "
        f"elevation={elevation}m, pressure={expected_pressure} hPa, "
        f"range=[{pressure_min}, {pressure_max}]"
    )

    return (pressure_min, pressure_max)
