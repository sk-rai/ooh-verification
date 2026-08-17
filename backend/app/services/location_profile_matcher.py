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
    

    def _point_to_segment_distance_meters(self, px, py, ax, ay, bx, by):
        """Approximate distance from point P to line segment A-B in meters."""
        import math
        # Convert to approximate meters (at given latitude)
        cos_lat = math.cos(math.radians(px))
        # Vector AB in meters
        abx = (bx - ax) * 111320 * cos_lat
        aby = (by - ay) * 110540
        # Vector AP in meters
        apx = (px - ax) * 111320 * cos_lat
        apy = (py - ay) * 110540
        ab_sq = abx * abx + aby * aby
        if ab_sq < 1e-10:
            return math.sqrt(apx * apx + apy * apy)
        t = max(0, min(1, (apx * abx + apy * aby) / ab_sq))
        # Closest point on segment
        cx = t * abx
        cy = t * aby
        dx = apx - cx
        dy = apy - cy
        return math.sqrt(dx * dx + dy * dy)

    def _check_bbox(self, lat, lon, profile):
        """Check if point is within bounding box."""
        ne_lat = getattr(profile, 'viewport_ne_lat', None)
        ne_lon = getattr(profile, 'viewport_ne_lon', None)
        sw_lat = getattr(profile, 'viewport_sw_lat', None)
        sw_lon = getattr(profile, 'viewport_sw_lon', None)
        if ne_lat and ne_lon and sw_lat and sw_lon:
            return sw_lat <= lat <= ne_lat and sw_lon <= lon <= ne_lon
        return None

    def _check_polygon(self, lat, lon, profile):
        """Ray casting - check if point is inside polygon."""
        polygon = getattr(profile, 'polygon_points', None)
        if not polygon or not isinstance(polygon, list) or len(polygon) < 3:
            return None
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            xi = polygon[i].get("lat", 0)
            yi = polygon[i].get("lon", 0)
            xj = polygon[j].get("lat", 0)
            yj = polygon[j].get("lon", 0)
            if ((yi > lon) != (yj > lon)) and (lat < (xj - xi) * (lon - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def _check_corridor(self, lat, lon, profile):
        """Check if point is within buffer distance of any segment in the route."""
        polygon = getattr(profile, 'polygon_points', None)
        buffer = getattr(profile, 'corridor_buffer_meters', None)
        if not polygon or not isinstance(polygon, list) or len(polygon) < 2 or not buffer:
            return None
        for i in range(len(polygon) - 1):
            dist = self._point_to_segment_distance_meters(
                lat, lon,
                polygon[i].get("lat", 0), polygon[i].get("lon", 0),
                polygon[i+1].get("lat", 0), polygon[i+1].get("lon", 0)
            )
            if dist <= buffer:
                return True
        return False

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
        # Check geofence type (bbox/polygon/corridor before circle fallback)
        geofence_type = getattr(location_profile, 'geofence_type', 'circle') if location_profile else 'circle'
        
        if location_profile and geofence_type != 'circle':
            lat = captured_data.get("latitude", 0)
            lon = captured_data.get("longitude", 0)
            if lat and lon:
                if geofence_type == "bbox":
                    result = self._check_bbox(lat, lon, location_profile)
                    if result is not None:
                        score = 90 if result else 10
                        return {"match_score": score, "distance_meters": 0 if result else 99999, "geofence_type": "bbox", "inside": result}
                elif geofence_type == "polygon":
                    result = self._check_polygon(lat, lon, location_profile)
                    if result is not None:
                        score = 90 if result else 10
                        return {"match_score": score, "distance_meters": 0 if result else 99999, "geofence_type": "polygon", "inside": result}
                elif geofence_type == "corridor":
                    result = self._check_corridor(lat, lon, location_profile)
                    if result is not None:
                        score = 90 if result else 10
                        return {"match_score": score, "distance_meters": 0 if result else 99999, "geofence_type": "corridor", "inside": result}

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
