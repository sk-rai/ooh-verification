"""
Location Profile Matching Service

Matches captured location data against expected location profiles.
Calculates confidence scores based on GPS, WiFi, cell towers, and environmental sensors.

**Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8**
"""

import math
from typing import Dict, List, Optional, Any
from datetime import datetime


class LocationProfileMatcher:
    """
    Service for matching captured location data against expected location profiles.
    
    Location profiles are OPTIONAL - if no profile exists, matching is skipped.
    """
    
    # Scoring weights (total = 100)
    GPS_WEIGHT = 40
    WIFI_WEIGHT = 30
    CELL_TOWER_WEIGHT = 20
    ENVIRONMENTAL_WEIGHT = 10
    
    # GPS scoring thresholds (meters)
    GPS_EXCELLENT_THRESHOLD = 50  # < 50m = full points
    GPS_POOR_THRESHOLD = 1000     # > 1000m = 0 points
    
    # WiFi matching thresholds
    WIFI_MIN_MATCHES = 3  # Minimum matches for high confidence
    
    def __init__(self):
        """Initialize the location profile matcher."""
        pass
    
    def match_location(
        self,
        captured_data: Dict[str, Any],
        location_profile: Optional[Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Match captured location data against expected location profile.
        
        Args:
            captured_data: Dictionary containing captured sensor data
                - latitude: float
                - longitude: float
                - wifi_bssids: List[str] (optional)
                - cell_tower_ids: List[str] (optional)
                - pressure: float (optional)
                - light_level: float (optional)
            location_profile: LocationProfile model instance (optional)
        
        Returns:
            Dictionary with match results or None if no profile:
                - match_score: float (0-100)
                - distance_meters: float
                - details: dict with component scores
            
            Returns None if location_profile is None (profiles are optional)
        """
        # Handle optional location profile
        if location_profile is None:
            return None
        
        # Initialize result
        result = {
            'match_score': 0.0,
            'distance_meters': 0.0,
            'details': {
                'gps_score': 0.0,
                'wifi_score': 0.0,
                'cell_tower_score': 0.0,
                'environmental_score': 0.0,
                'gps_distance_meters': 0.0,
                'wifi_matches': 0,
                'cell_tower_matches': 0,
                'pressure_match': False,
                'light_match': False
            }
        }
        
        # Calculate GPS distance and score
        if (captured_data.get('latitude') is not None and 
            captured_data.get('longitude') is not None and
            location_profile.expected_latitude is not None and
            location_profile.expected_longitude is not None):
            
            distance = self.calculate_haversine_distance(
                captured_data['latitude'],
                captured_data['longitude'],
                location_profile.expected_latitude,
                location_profile.expected_longitude
            )
            
            result['distance_meters'] = distance
            result['details']['gps_distance_meters'] = distance
            result['details']['gps_score'] = self._calculate_gps_score(distance)
        
        # Calculate WiFi BSSID matches and score
        if captured_data.get('wifi_bssids') and location_profile.expected_wifi_bssids:
            wifi_matches = self._count_wifi_matches(
                captured_data['wifi_bssids'],
                location_profile.expected_wifi_bssids
            )
            result['details']['wifi_matches'] = wifi_matches
            result['details']['wifi_score'] = self._calculate_wifi_score(wifi_matches)
        
        # Calculate cell tower matches and score
        if captured_data.get('cell_tower_ids') and location_profile.expected_cell_tower_ids:
            cell_matches = self._count_cell_tower_matches(
                captured_data['cell_tower_ids'],
                location_profile.expected_cell_tower_ids
            )
            result['details']['cell_tower_matches'] = cell_matches
            result['details']['cell_tower_score'] = self._calculate_cell_tower_score(cell_matches)
        
        # Calculate environmental sensor score
        env_score = 0.0
        env_components = 0

        # Check pressure range (using min/max columns)
        if (captured_data.get('pressure') is not None and
                location_profile.expected_pressure_min is not None and
                location_profile.expected_pressure_max is not None):
            env_components += 1
            if (location_profile.expected_pressure_min
                    <= captured_data['pressure']
                    <= location_profile.expected_pressure_max):
                result['details']['pressure_match'] = True
                env_score += 1

        # Check light level range (using min/max columns)
        if (captured_data.get('light_level') is not None and
                location_profile.expected_light_min is not None and
                location_profile.expected_light_max is not None):
            env_components += 1
            if (location_profile.expected_light_min
                    <= captured_data['light_level']
                    <= location_profile.expected_light_max):
                result['details']['light_match'] = True
                env_score += 1

        # Calculate environmental score
        if env_components > 0:
            result['details']['environmental_score'] = (
                (env_score / env_components) * self.ENVIRONMENTAL_WEIGHT
            )
        
        # Calculate total match score
        result['match_score'] = (
            result['details']['gps_score'] +
            result['details']['wifi_score'] +
            result['details']['cell_tower_score'] +
            result['details']['environmental_score']
        )
        
        return result
    
    def calculate_haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate distance between two GPS coordinates using Haversine formula.
        
        Args:
            lat1: Latitude of first point (degrees)
            lon1: Longitude of first point (degrees)
            lat2: Latitude of second point (degrees)
            lon2: Longitude of second point (degrees)
        
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
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        
        return distance
    
    def _calculate_gps_score(self, distance_meters: float) -> float:
        """
        Calculate GPS match score based on distance.
        
        Args:
            distance_meters: Distance from expected location
        
        Returns:
            Score from 0 to GPS_WEIGHT (40 points)
        """
        if distance_meters <= self.GPS_EXCELLENT_THRESHOLD:
            return self.GPS_WEIGHT
        elif distance_meters >= self.GPS_POOR_THRESHOLD:
            return 0.0
        else:
            # Linear interpolation between thresholds
            ratio = (self.GPS_POOR_THRESHOLD - distance_meters) / (
                self.GPS_POOR_THRESHOLD - self.GPS_EXCELLENT_THRESHOLD
            )
            return ratio * self.GPS_WEIGHT
    
    def _count_wifi_matches(
        self,
        captured_bssids: List[str],
        expected_bssids: List[str]
    ) -> int:
        """
        Count matching WiFi BSSIDs.
        
        Args:
            captured_bssids: List of captured BSSIDs
            expected_bssids: List of expected BSSIDs
        
        Returns:
            Number of matching BSSIDs
        """
        captured_set = set(captured_bssids)
        expected_set = set(expected_bssids)
        return len(captured_set.intersection(expected_set))
    
    def _calculate_wifi_score(self, match_count: int) -> float:
        """
        Calculate WiFi match score based on number of matching BSSIDs.
        
        Args:
            match_count: Number of matching BSSIDs
        
        Returns:
            Score from 0 to WIFI_WEIGHT (30 points)
        """
        if match_count >= self.WIFI_MIN_MATCHES:
            # Full points for 3+ matches
            return self.WIFI_WEIGHT
        elif match_count == 2:
            # 70% for 2 matches
            return self.WIFI_WEIGHT * 0.7
        elif match_count == 1:
            # 40% for 1 match
            return self.WIFI_WEIGHT * 0.4
        else:
            return 0.0
    
    def _count_cell_tower_matches(
        self,
        captured_ids: List[str],
        expected_ids: List[str]
    ) -> int:
        """
        Count matching cell tower IDs.
        
        Args:
            captured_ids: List of captured cell tower IDs
            expected_ids: List of expected cell tower IDs
        
        Returns:
            Number of matching cell tower IDs
        """
        captured_set = set(captured_ids)
        expected_set = set(expected_ids)
        return len(captured_set.intersection(expected_set))
    
    def _calculate_cell_tower_score(self, match_count: int) -> float:
        """
        Calculate cell tower match score.
        
        Args:
            match_count: Number of matching cell tower IDs
        
        Returns:
            Score from 0 to CELL_TOWER_WEIGHT (20 points)
        """
        if match_count >= 2:
            # Full points for 2+ matches
            return self.CELL_TOWER_WEIGHT
        elif match_count == 1:
            # 60% for 1 match
            return self.CELL_TOWER_WEIGHT * 0.6
        else:
            return 0.0
    
    def _is_in_range(self, value: float, range_dict: Dict[str, float]) -> bool:
        """
        Check if a value is within expected range.
        
        Args:
            value: Captured sensor value
            range_dict: Dictionary with 'min' and 'max' keys
        
        Returns:
            True if value is within range
        """
        min_val = range_dict.get('min')
        max_val = range_dict.get('max')
        
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False
        
        return True
