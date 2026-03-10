"""
Location Verification Service - Verify photo locations against campaign locations.

Uses Haversine formula to calculate distance between GPS coordinates.
"""
import math
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.campaign_location import CampaignLocation


class LocationVerificationResult:
    """Result of location verification."""
    
    def __init__(
        self,
        is_valid: bool,
        distance_meters: float,
        nearest_location: Optional[CampaignLocation] = None,
        message: str = ""
    ):
        self.is_valid = is_valid
        self.distance_meters = distance_meters
        self.nearest_location = nearest_location
        self.message = message
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "distance_meters": round(self.distance_meters, 2),
            "nearest_location_id": str(self.nearest_location.location_id) if self.nearest_location else None,
            "nearest_location_name": self.nearest_location.name if self.nearest_location else None,
            "message": self.message
        }


class LocationVerificationService:
    """
    Service for verifying photo locations against campaign locations.
    
    Features:
    - Calculate distance between GPS coordinates
    - Find nearest campaign location
    - Verify if photo is within acceptable radius
    """
    
    @staticmethod
    def calculate_distance(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate distance between two GPS coordinates using Haversine formula.
        
        Args:
            lat1: Latitude of first point
            lon1: Longitude of first point
            lat2: Latitude of second point
            lon2: Longitude of second point
            
        Returns:
            Distance in meters
        """
        # Earth's radius in meters
        R = 6371000
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        # Haversine formula
        a = (
            math.sin(delta_lat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) *
            math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return distance
    
    async def verify_location(
        self,
        db: AsyncSession,
        campaign_id: str,
        photo_latitude: float,
        photo_longitude: float
    ) -> LocationVerificationResult:
        """
        Verify if photo location is within acceptable range of any campaign location.
        
        Args:
            db: Database session
            campaign_id: Campaign UUID
            photo_latitude: Photo's GPS latitude
            photo_longitude: Photo's GPS longitude
            
        Returns:
            LocationVerificationResult with validation status
        """
        # Get all locations for this campaign
        result = await db.execute(
            select(CampaignLocation).where(
                CampaignLocation.campaign_id == campaign_id
            )
        )
        locations = result.scalars().all()
        
        if not locations:
            return LocationVerificationResult(
                is_valid=True,  # No locations defined = accept any location
                distance_meters=0,
                message="No campaign locations defined - location check skipped"
            )
        
        # Find nearest location and check if within radius
        nearest_location = None
        min_distance = float('inf')
        
        for location in locations:
            distance = self.calculate_distance(
                photo_latitude,
                photo_longitude,
                location.latitude,
                location.longitude
            )
            
            if distance < min_distance:
                min_distance = distance
                nearest_location = location
        
        # Check if within acceptable radius
        if nearest_location:
            is_within_radius = min_distance <= nearest_location.verification_radius_meters
            
            if is_within_radius:
                message = f"Photo location verified within {nearest_location.verification_radius_meters}m of '{nearest_location.name}'"
            else:
                message = f"Photo location is {round(min_distance, 2)}m from nearest location '{nearest_location.name}' (max allowed: {nearest_location.verification_radius_meters}m)"
            
            return LocationVerificationResult(
                is_valid=is_within_radius,
                distance_meters=min_distance,
                nearest_location=nearest_location,
                message=message
            )
        
        return LocationVerificationResult(
            is_valid=False,
            distance_meters=min_distance,
            message="No valid campaign locations found"
        )
    
    async def find_nearest_location(
        self,
        db: AsyncSession,
        campaign_id: str,
        latitude: float,
        longitude: float
    ) -> Tuple[Optional[CampaignLocation], float]:
        """
        Find the nearest campaign location to given coordinates.
        
        Args:
            db: Database session
            campaign_id: Campaign UUID
            latitude: Target latitude
            longitude: Target longitude
            
        Returns:
            Tuple of (nearest_location, distance_in_meters)
        """
        result = await db.execute(
            select(CampaignLocation).where(
                CampaignLocation.campaign_id == campaign_id
            )
        )
        locations = result.scalars().all()
        
        if not locations:
            return None, 0
        
        nearest_location = None
        min_distance = float('inf')
        
        for location in locations:
            distance = self.calculate_distance(
                latitude,
                longitude,
                location.latitude,
                location.longitude
            )
            
            if distance < min_distance:
                min_distance = distance
                nearest_location = location
        
        return nearest_location, min_distance
    
    async def get_locations_within_radius(
        self,
        db: AsyncSession,
        campaign_id: str,
        latitude: float,
        longitude: float,
        radius_meters: float
    ) -> List[Tuple[CampaignLocation, float]]:
        """
        Get all campaign locations within specified radius.
        
        Args:
            db: Database session
            campaign_id: Campaign UUID
            latitude: Center latitude
            longitude: Center longitude
            radius_meters: Search radius in meters
            
        Returns:
            List of (location, distance) tuples sorted by distance
        """
        result = await db.execute(
            select(CampaignLocation).where(
                CampaignLocation.campaign_id == campaign_id
            )
        )
        locations = result.scalars().all()
        
        locations_within_radius = []
        
        for location in locations:
            distance = self.calculate_distance(
                latitude,
                longitude,
                location.latitude,
                location.longitude
            )
            
            if distance <= radius_meters:
                locations_within_radius.append((location, distance))
        
        # Sort by distance
        locations_within_radius.sort(key=lambda x: x[1])
        
        return locations_within_radius


# Singleton instance
_location_verification_service: Optional[LocationVerificationService] = None


def get_location_verification_service() -> LocationVerificationService:
    """Get or create location verification service singleton."""
    global _location_verification_service
    if _location_verification_service is None:
        _location_verification_service = LocationVerificationService()
    return _location_verification_service
