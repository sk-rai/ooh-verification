"""
Geocoding Service - Convert addresses to coordinates and vice versa.

Supports multiple providers:
- Google Maps Geocoding API (primary)
- OpenStreetMap Nominatim (fallback, free)
"""
import httpx
import os
from typing import Optional, Dict, Any, List
from datetime import datetime


class GeocodingResult:
    """Structured geocoding result."""
    
    def __init__(
        self,
        latitude: float,
        longitude: float,
        formatted_address: str,
        accuracy: str = "APPROXIMATE",
        place_id: Optional[str] = None,
        address_components: Optional[Dict[str, str]] = None
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.formatted_address = formatted_address
        self.accuracy = accuracy
        self.place_id = place_id
        self.address_components = address_components or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "formatted_address": self.formatted_address,
            "accuracy": self.accuracy,
            "place_id": self.place_id,
            "city": self.address_components.get("city"),
            "state": self.address_components.get("state"),
            "country": self.address_components.get("country"),
            "postal_code": self.address_components.get("postal_code"),
        }


class GeocodingService:
    """
    Geocoding service with multiple provider support.
    
    Usage:
        service = GeocodingService()
        result = await service.geocode("1600 Amphitheatre Parkway, Mountain View, CA")
        reverse = await service.reverse_geocode(37.4224764, -122.0842499)
    """
    
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.use_google = bool(self.google_api_key)
        
    async def geocode(self, address: str) -> Optional[GeocodingResult]:
        """
        Convert address to coordinates.
        
        Args:
            address: Full address string
            
        Returns:
            GeocodingResult or None if geocoding fails
        """
        if self.use_google:
            result = await self._geocode_google(address)
            if result:
                return result
        
        # Fallback to OpenStreetMap Nominatim (free, no API key required)
        return await self._geocode_nominatim(address)
    
    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[GeocodingResult]:
        """
        Convert coordinates to address.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            GeocodingResult or None if reverse geocoding fails
        """
        if self.use_google:
            result = await self._reverse_geocode_google(latitude, longitude)
            if result:
                return result
        
        # Fallback to OpenStreetMap Nominatim
        return await self._reverse_geocode_nominatim(latitude, longitude)
    
    async def _geocode_google(self, address: str) -> Optional[GeocodingResult]:
        """Geocode using Google Maps API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params={
                        "address": address,
                        "key": self.google_api_key
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    return None
                
                data = response.json()
                
                if data["status"] != "OK" or not data.get("results"):
                    return None
                
                result = data["results"][0]
                location = result["geometry"]["location"]
                
                # Extract address components
                components = {}
                for component in result.get("address_components", []):
                    types = component.get("types", [])
                    if "locality" in types:
                        components["city"] = component["long_name"]
                    elif "administrative_area_level_1" in types:
                        components["state"] = component["long_name"]
                    elif "country" in types:
                        components["country"] = component["long_name"]
                    elif "postal_code" in types:
                        components["postal_code"] = component["long_name"]
                
                return GeocodingResult(
                    latitude=location["lat"],
                    longitude=location["lng"],
                    formatted_address=result["formatted_address"],
                    accuracy=result["geometry"]["location_type"],
                    place_id=result.get("place_id"),
                    address_components=components
                )
        except Exception as e:
            print(f"Google geocoding error: {e}")
            return None
    
    async def _geocode_nominatim(self, address: str) -> Optional[GeocodingResult]:
        """Geocode using OpenStreetMap Nominatim (free)."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={
                        "q": address,
                        "format": "json",
                        "limit": 1,
                        "addressdetails": 1
                    },
                    headers={
                        "User-Agent": "TrustCapture/1.0"  # Required by Nominatim
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    return None
                
                data = response.json()
                
                if not data:
                    return None
                
                result = data[0]
                address_data = result.get("address", {})
                
                # Extract address components
                components = {
                    "city": address_data.get("city") or address_data.get("town") or address_data.get("village"),
                    "state": address_data.get("state"),
                    "country": address_data.get("country"),
                    "postal_code": address_data.get("postcode"),
                }
                
                return GeocodingResult(
                    latitude=float(result["lat"]),
                    longitude=float(result["lon"]),
                    formatted_address=result["display_name"],
                    accuracy="APPROXIMATE",
                    place_id=result.get("place_id"),
                    address_components=components
                )
        except Exception as e:
            print(f"Nominatim geocoding error: {e}")
            return None
    
    async def _reverse_geocode_google(self, latitude: float, longitude: float) -> Optional[GeocodingResult]:
        """Reverse geocode using Google Maps API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params={
                        "latlng": f"{latitude},{longitude}",
                        "key": self.google_api_key
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    return None
                
                data = response.json()
                
                if data["status"] != "OK" or not data.get("results"):
                    return None
                
                result = data["results"][0]
                location = result["geometry"]["location"]
                
                # Extract address components
                components = {}
                for component in result.get("address_components", []):
                    types = component.get("types", [])
                    if "locality" in types:
                        components["city"] = component["long_name"]
                    elif "administrative_area_level_1" in types:
                        components["state"] = component["long_name"]
                    elif "country" in types:
                        components["country"] = component["long_name"]
                    elif "postal_code" in types:
                        components["postal_code"] = component["long_name"]
                
                return GeocodingResult(
                    latitude=location["lat"],
                    longitude=location["lng"],
                    formatted_address=result["formatted_address"],
                    accuracy=result["geometry"]["location_type"],
                    place_id=result.get("place_id"),
                    address_components=components
                )
        except Exception as e:
            print(f"Google reverse geocoding error: {e}")
            return None
    
    async def _reverse_geocode_nominatim(self, latitude: float, longitude: float) -> Optional[GeocodingResult]:
        """Reverse geocode using OpenStreetMap Nominatim (free)."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://nominatim.openstreetmap.org/reverse",
                    params={
                        "lat": latitude,
                        "lon": longitude,
                        "format": "json",
                        "addressdetails": 1
                    },
                    headers={
                        "User-Agent": "TrustCapture/1.0"
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    return None
                
                result = response.json()
                address_data = result.get("address", {})
                
                # Extract address components
                components = {
                    "city": address_data.get("city") or address_data.get("town") or address_data.get("village"),
                    "state": address_data.get("state"),
                    "country": address_data.get("country"),
                    "postal_code": address_data.get("postcode"),
                }
                
                return GeocodingResult(
                    latitude=float(result["lat"]),
                    longitude=float(result["lon"]),
                    formatted_address=result["display_name"],
                    accuracy="APPROXIMATE",
                    place_id=result.get("place_id"),
                    address_components=components
                )
        except Exception as e:
            print(f"Nominatim reverse geocoding error: {e}")
            return None


# Singleton instance
_geocoding_service: Optional[GeocodingService] = None


def get_geocoding_service() -> GeocodingService:
    """Get or create geocoding service singleton."""
    global _geocoding_service
    if _geocoding_service is None:
        _geocoding_service = GeocodingService()
    return _geocoding_service
