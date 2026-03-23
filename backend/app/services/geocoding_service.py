"""
Geocoding service for bidirectional address-coordinate conversion.

Features:
- Forward geocoding: address -> coordinates
- Reverse geocoding: coordinates -> address
- Dual provider: Google Maps (primary) + Nominatim (fallback)
- Caching for performance
- Batch processing support

Requirements:
- Property 40: Geocoding consistency
"""

import logging
import os
from typing import Tuple, Optional, List, Dict, Any
import httpx
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class GeocodingResult:
    """Result from geocoding operation."""

    def __init__(
        self,
        latitude: float,
        longitude: float,
        formatted_address: str,
        address_components: Optional[Dict[str, str]] = None,
        place_id: Optional[str] = None,
        accuracy: Optional[str] = None,
        provider: str = "unknown"
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.formatted_address = formatted_address
        self.address_components = address_components or {}
        self.place_id = place_id
        self.accuracy = accuracy
        self.provider = provider

    def to_dict(self) -> Dict[str, Any]:
        return {

            "latitude": self.latitude,
            "longitude": self.longitude,
            "formatted_address": self.formatted_address,
            "address_components": self.address_components,
            "place_id": self.place_id,
            "accuracy": self.accuracy,
            "provider": self.provider
        }


class GeocodingService:
    """Service for bidirectional address-coordinate conversion."""

    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.cache: Dict[str, Tuple[GeocodingResult, datetime]] = {}
        self.cache_ttl = timedelta(days=30)
        self.timeout = 10.0

        if self.google_api_key:
            logger.info("Google Maps API key configured")
        else:
            logger.warning("Google Maps API key not configured, will use Nominatim only")

    async def geocode_address(self, address: str, use_cache: bool = True) -> GeocodingResult:
        """Forward geocoding: Convert address to coordinates."""
        if not address or not address.strip():
            raise GeocodingError("Address cannot be empty")

        address = address.strip()

        # Check cache
        if use_cache:
            cached = self._get_from_cache(f"forward:{address}")
            if cached:
                logger.info(f"Cache hit for address: {address}")
                return cached

        # Try Google Maps first
        if self.google_api_key:
            try:
                result = await self._google_forward_geocode(address)
                if result:
                    self._add_to_cache(f"forward:{address}", result)
                    return result
            except Exception as e:
                logger.warning(f"Google Maps geocoding failed: {e}")

        # Fallback to Nominatim
        try:
            result = await self._nominatim_forward_geocode(address)
            if result:
                self._add_to_cache(f"forward:{address}", result)
                return result
        except Exception as e:
            logger.error(f"Nominatim geocoding failed: {e}")

        raise GeocodingError(
            f"Failed to geocode address '{address}' with all providers. "
            "Please provide coordinates directly."
        )

    async def reverse_geocode(
        self, latitude: float, longitude: float, use_cache: bool = True
    ) -> GeocodingResult:
        """Reverse geocoding: Convert coordinates to address."""
        if not (-90 <= latitude <= 90):
            raise GeocodingError(f"Invalid latitude: {latitude}. Must be between -90 and 90")
        if not (-180 <= longitude <= 180):
            raise GeocodingError(f"Invalid longitude: {longitude}. Must be between -180 and 180")

        cache_key = f"reverse:{latitude:.6f},{longitude:.6f}"
        if use_cache:
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.info(f"Cache hit for coordinates: ({latitude}, {longitude})")
                return cached

        # Try Google Maps first
        if self.google_api_key:
            try:
                result = await self._google_reverse_geocode(latitude, longitude)
                if result:
                    self._add_to_cache(cache_key, result)
                    return result
            except Exception as e:
                logger.warning(f"Google Maps reverse geocoding failed: {e}")

        # Fallback to Nominatim
        try:
            result = await self._nominatim_reverse_geocode(latitude, longitude)
            if result:
                self._add_to_cache(cache_key, result)
                return result
        except Exception as e:
            logger.error(f"Nominatim reverse geocoding failed: {e}")

        raise GeocodingError(
            f"Failed to reverse geocode coordinates ({latitude}, {longitude}) with all providers"
        )

    async def batch_geocode_addresses(
        self, addresses: List[str], use_cache: bool = True
    ) -> List[Optional[GeocodingResult]]:
        """Batch forward geocode multiple addresses."""
        results = []
        for address in addresses:
            try:
                result = await self.geocode_address(address, use_cache=use_cache)
                results.append(result)
            except GeocodingError as e:
                logger.warning(f"Failed to geocode '{address}': {e}")
                results.append(None)
        return results

    async def batch_reverse_geocode(
        self, coordinates: List[Tuple[float, float]], use_cache: bool = True
    ) -> List[Optional[GeocodingResult]]:
        """Batch reverse geocode multiple coordinates."""
        results = []
        for lat, lon in coordinates:
            try:
                result = await self.reverse_geocode(lat, lon, use_cache=use_cache)
                results.append(result)
            except GeocodingError as e:
                logger.warning(f"Failed to reverse geocode ({lat}, {lon}): {e}")
                results.append(None)
        return results


    async def _google_forward_geocode(self, address: str) -> Optional[GeocodingResult]:
        """Forward geocode using Google Maps API."""
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"address": address, "key": self.google_api_key}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data["status"] != "OK" or not data.get("results"):
            logger.warning(f"Google Maps API returned status: {data['status']}")
            return None

        result = data["results"][0]
        location = result["geometry"]["location"]

        components = {}
        for component in result.get("address_components", []):
            types = component.get("types", [])
            if "street_number" in types:
                components["street_number"] = component["long_name"]
            elif "route" in types:
                components["street"] = component["long_name"]
            elif "locality" in types:
                components["city"] = component["long_name"]
            elif "administrative_area_level_1" in types:
                components["state"] = component["short_name"]
            elif "country" in types:
                components["country"] = component["long_name"]
                components["country_code"] = component["short_name"]
            elif "postal_code" in types:
                components["postal_code"] = component["long_name"]

        return GeocodingResult(
            latitude=location["lat"],
            longitude=location["lng"],
            formatted_address=result["formatted_address"],
            address_components=components,
            place_id=result.get("place_id"),
            accuracy=result["geometry"].get("location_type"),
            provider="google_maps"
        )

    async def _google_reverse_geocode(
        self, latitude: float, longitude: float
    ) -> Optional[GeocodingResult]:
        """Reverse geocode using Google Maps API."""
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"latlng": f"{latitude},{longitude}", "key": self.google_api_key}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data["status"] != "OK" or not data.get("results"):
            logger.warning(f"Google Maps API returned status: {data['status']}")
            return None

        result = data["results"][0]
        location = result["geometry"]["location"]

        components = {}
        for component in result.get("address_components", []):
            types = component.get("types", [])
            if "street_number" in types:
                components["street_number"] = component["long_name"]
            elif "route" in types:
                components["street"] = component["long_name"]
            elif "locality" in types:
                components["city"] = component["long_name"]
            elif "administrative_area_level_1" in types:
                components["state"] = component["short_name"]
            elif "country" in types:
                components["country"] = component["long_name"]
                components["country_code"] = component["short_name"]
            elif "postal_code" in types:
                components["postal_code"] = component["long_name"]

        return GeocodingResult(
            latitude=location["lat"],
            longitude=location["lng"],
            formatted_address=result["formatted_address"],
            address_components=components,
            place_id=result.get("place_id"),
            accuracy=result["geometry"].get("location_type"),
            provider="google_maps"
        )


    async def _nominatim_forward_geocode(self, address: str) -> Optional[GeocodingResult]:
        """Forward geocode using Nominatim (OpenStreetMap)."""
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json", "addressdetails": 1, "limit": 1}
        headers = {"User-Agent": "TrustCapture/1.0"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        if not data:
            return None

        result = data[0]
        address_data = result.get("address", {})

        components = {
            "street_number": address_data.get("house_number", ""),
            "street": address_data.get("road", ""),
            "city": address_data.get("city") or address_data.get("town") or address_data.get("village", ""),
            "state": address_data.get("state", ""),
            "country": address_data.get("country", ""),
            "country_code": address_data.get("country_code", "").upper(),
            "postal_code": address_data.get("postcode", "")
        }

        return GeocodingResult(
            latitude=float(result["lat"]),
            longitude=float(result["lon"]),
            formatted_address=result.get("display_name", address),
            address_components=components,
            place_id=result.get("place_id"),
            accuracy=result.get("type"),
            provider="nominatim"
        )

    async def _nominatim_reverse_geocode(
        self, latitude: float, longitude: float
    ) -> Optional[GeocodingResult]:
        """Reverse geocode using Nominatim (OpenStreetMap)."""
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"lat": latitude, "lon": longitude, "format": "json", "addressdetails": 1}
        headers = {"User-Agent": "TrustCapture/1.0"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        if "error" in data:
            return None

        address_data = data.get("address", {})

        components = {
            "street_number": address_data.get("house_number", ""),
            "street": address_data.get("road", ""),
            "city": address_data.get("city") or address_data.get("town") or address_data.get("village", ""),
            "state": address_data.get("state", ""),
            "country": address_data.get("country", ""),
            "country_code": address_data.get("country_code", "").upper(),
            "postal_code": address_data.get("postcode", "")
        }

        return GeocodingResult(
            latitude=latitude,
            longitude=longitude,
            formatted_address=data.get("display_name", f"{latitude}, {longitude}"),
            address_components=components,
            place_id=data.get("place_id"),
            accuracy=data.get("type"),
            provider="nominatim"
        )

    async def lookup_address_from_db(self, address: str, db) -> Optional[GeocodingResult]:
        """Look up address in campaign_locations table before hitting external API."""
        try:
            from sqlalchemy import select, func
            from app.models.campaign_location import CampaignLocation
            # Case-insensitive partial match
            result = await db.execute(
                select(CampaignLocation)
                .where(func.lower(CampaignLocation.address).contains(address.lower().strip()))
                .limit(1)
            )
            loc = result.scalar_one_or_none()
            if loc and loc.latitude and loc.longitude:
                logger.info(f"DB cache hit for address: {address}")
                return GeocodingResult(
                    latitude=loc.latitude,
                    longitude=loc.longitude,
                    formatted_address=loc.address,
                    address_components={
                        "city": loc.city or "",
                        "state": loc.state or "",
                        "country": loc.country or "",
                        "postal_code": loc.postal_code or "",
                    },
                    place_id=loc.place_id,
                    accuracy=loc.geocoding_accuracy,
                    provider="db_cache"
                )
        except Exception as e:
            logger.warning(f"DB lookup failed for address '{address}': {e}")
        return None

    async def lookup_coords_from_db(self, latitude: float, longitude: float, db, radius_deg: float = 0.001) -> Optional[GeocodingResult]:
        """Look up coordinates in campaign_locations table (within ~100m radius)."""
        try:
            from sqlalchemy import select, and_
            from app.models.campaign_location import CampaignLocation
            result = await db.execute(
                select(CampaignLocation)
                .where(and_(
                    CampaignLocation.latitude.between(latitude - radius_deg, latitude + radius_deg),
                    CampaignLocation.longitude.between(longitude - radius_deg, longitude + radius_deg),
                ))
                .limit(1)
            )
            loc = result.scalar_one_or_none()
            if loc and loc.address:
                logger.info(f"DB cache hit for coords: ({latitude}, {longitude})")
                return GeocodingResult(
                    latitude=loc.latitude,
                    longitude=loc.longitude,
                    formatted_address=loc.address,
                    address_components={
                        "city": loc.city or "",
                        "state": loc.state or "",
                        "country": loc.country or "",
                        "postal_code": loc.postal_code or "",
                    },
                    place_id=loc.place_id,
                    accuracy=loc.geocoding_accuracy,
                    provider="db_cache"
                )
        except Exception as e:
            logger.warning(f"DB lookup failed for coords ({latitude}, {longitude}): {e}")
        return None

    def _get_from_cache(self, key: str) -> Optional[GeocodingResult]:
        """Get result from cache if not expired."""
        if key in self.cache:
            result, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.cache_ttl:
                return result
            else:
                del self.cache[key]
        return None

    def _add_to_cache(self, key: str, result: GeocodingResult):
        """Add result to cache with timestamp."""
        self.cache[key] = (result, datetime.now())

    def clear_cache(self):
        """Clear all cached results."""
        self.cache.clear()
        logger.info("Geocoding cache cleared")


class GeocodingError(Exception):
    """Raised when geocoding fails."""
    pass


_geocoding_service = None


def get_geocoding_service() -> GeocodingService:
    """Get or create the geocoding service singleton."""
    global _geocoding_service
    if _geocoding_service is None:
        _geocoding_service = GeocodingService()
    return _geocoding_service
