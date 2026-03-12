"""
Unit tests for Location Profile Matching Service

Tests GPS distance calculation, WiFi/cell tower matching, environmental sensors,
and confidence score calculation.

**Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8**
"""

import pytest
import math
from unittest.mock import Mock
from app.services.location_profile_matcher import LocationProfileMatcher


class TestHaversineDistance:
    """Test GPS distance calculation using Haversine formula."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.matcher = LocationProfileMatcher()
    
    def test_same_location_zero_distance(self):
        """Test that same coordinates return zero distance."""
        distance = self.matcher.calculate_haversine_distance(
            40.7128, -74.0060,  # New York
            40.7128, -74.0060   # Same location
        )
        assert distance == 0.0
    
    def test_known_distance_accuracy(self):
        """Test distance calculation accuracy with known coordinates."""
        # New York to Los Angeles (approx 3936 km)
        distance = self.matcher.calculate_haversine_distance(
            40.7128, -74.0060,  # New York
            34.0522, -118.2437  # Los Angeles
        )
        # Allow 1% margin of error
        expected = 3936000  # meters
        assert abs(distance - expected) < expected * 0.01
    
    def test_short_distance_accuracy(self):
        """Test accuracy for short distances (< 1km)."""
        # Two points approximately 500m apart
        distance = self.matcher.calculate_haversine_distance(
            40.7128, -74.0060,
            40.7173, -74.0060  # ~500m north
        )
        assert 450 < distance < 550
    
    def test_equator_crossing(self):
        """Test distance calculation across equator."""
        distance = self.matcher.calculate_haversine_distance(
            -1.0, 0.0,  # South of equator
            1.0, 0.0    # North of equator
        )
        # Approximately 222 km
        assert 220000 < distance < 224000
    
    def test_antipodal_points(self):
        """Test maximum distance (opposite sides of Earth)."""
        distance = self.matcher.calculate_haversine_distance(
            0.0, 0.0,
            0.0, 180.0
        )
        # Half Earth's circumference (approx 20,000 km)
        assert 19900000 < distance < 20100000


class TestGPSScoring:
    """Test GPS distance scoring."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.matcher = LocationProfileMatcher()
    
    def test_excellent_distance_full_score(self):
        """Test that distances under 50m get full GPS score."""
        score = self.matcher._calculate_gps_score(25.0)
        assert score == self.matcher.GPS_WEIGHT
    
    def test_poor_distance_zero_score(self):
        """Test that distances over 1000m get zero score."""
        score = self.matcher._calculate_gps_score(1500.0)
        assert score == 0.0
    
    def test_medium_distance_interpolated_score(self):
        """Test linear interpolation for medium distances."""
        # 500m should be roughly halfway between thresholds
        score = self.matcher._calculate_gps_score(500.0)
        expected = self.matcher.GPS_WEIGHT * 0.5
        assert abs(score - expected) < 2.0  # Allow small margin
    
    def test_boundary_excellent_threshold(self):
        """Test score at excellent threshold boundary."""
        score = self.matcher._calculate_gps_score(50.0)
        assert score == self.matcher.GPS_WEIGHT
    
    def test_boundary_poor_threshold(self):
        """Test score at poor threshold boundary."""
        score = self.matcher._calculate_gps_score(1000.0)
        assert score == 0.0


class TestWiFiMatching:
    """Test WiFi BSSID matching."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.matcher = LocationProfileMatcher()
    
    def test_no_matches(self):
        """Test zero WiFi matches."""
        captured = ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]
        expected = ["FF:FF:FF:FF:FF:01", "FF:FF:FF:FF:FF:02"]
        
        matches = self.matcher._count_wifi_matches(captured, expected)
        assert matches == 0
        
        score = self.matcher._calculate_wifi_score(matches)
        assert score == 0.0
    
    def test_one_match(self):
        """Test single WiFi match."""
        captured = ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]
        expected = ["AA:BB:CC:DD:EE:01", "FF:FF:FF:FF:FF:02"]
        
        matches = self.matcher._count_wifi_matches(captured, expected)
        assert matches == 1
        
        score = self.matcher._calculate_wifi_score(matches)
        assert score == self.matcher.WIFI_WEIGHT * 0.4
    
    def test_two_matches(self):
        """Test two WiFi matches."""
        captured = ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:03"]
        expected = ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02", "FF:FF:FF:FF:FF:03"]
        
        matches = self.matcher._count_wifi_matches(captured, expected)
        assert matches == 2
        
        score = self.matcher._calculate_wifi_score(matches)
        assert score == self.matcher.WIFI_WEIGHT * 0.7
    
    def test_three_or_more_matches_full_score(self):
        """Test that 3+ WiFi matches get full score."""
        captured = ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:03"]
        expected = ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:03"]
        
        matches = self.matcher._count_wifi_matches(captured, expected)
        assert matches == 3
        
        score = self.matcher._calculate_wifi_score(matches)
        assert score == self.matcher.WIFI_WEIGHT
    
    def test_case_sensitive_matching(self):
        """Test that BSSID matching is case-sensitive."""
        captured = ["aa:bb:cc:dd:ee:01"]
        expected = ["AA:BB:CC:DD:EE:01"]
        
        matches = self.matcher._count_wifi_matches(captured, expected)
        assert matches == 0


class TestCellTowerMatching:
    """Test cell tower ID matching."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.matcher = LocationProfileMatcher()
    
    def test_no_matches(self):
        """Test zero cell tower matches."""
        captured = ["tower_001", "tower_002"]
        expected = ["tower_999", "tower_998"]
        
        matches = self.matcher._count_cell_tower_matches(captured, expected)
        assert matches == 0
        
        score = self.matcher._calculate_cell_tower_score(matches)
        assert score == 0.0
    
    def test_one_match(self):
        """Test single cell tower match."""
        captured = ["tower_001", "tower_002"]
        expected = ["tower_001", "tower_999"]
        
        matches = self.matcher._count_cell_tower_matches(captured, expected)
        assert matches == 1
        
        score = self.matcher._calculate_cell_tower_score(matches)
        assert score == self.matcher.CELL_TOWER_WEIGHT * 0.6
    
    def test_two_or_more_matches_full_score(self):
        """Test that 2+ cell tower matches get full score."""
        captured = ["tower_001", "tower_002", "tower_003"]
        expected = ["tower_001", "tower_002", "tower_999"]
        
        matches = self.matcher._count_cell_tower_matches(captured, expected)
        assert matches == 2
        
        score = self.matcher._calculate_cell_tower_score(matches)
        assert score == self.matcher.CELL_TOWER_WEIGHT


class TestEnvironmentalSensors:
    """Test environmental sensor range matching."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.matcher = LocationProfileMatcher()
    
    def test_value_within_range(self):
        """Test value within expected range."""
        range_dict = {'min': 1000.0, 'max': 1020.0}
        assert self.matcher._is_in_range(1010.0, range_dict) is True
    
    def test_value_below_range(self):
        """Test value below expected range."""
        range_dict = {'min': 1000.0, 'max': 1020.0}
        assert self.matcher._is_in_range(990.0, range_dict) is False
    
    def test_value_above_range(self):
        """Test value above expected range."""
        range_dict = {'min': 1000.0, 'max': 1020.0}
        assert self.matcher._is_in_range(1030.0, range_dict) is False
    
    def test_value_at_min_boundary(self):
        """Test value at minimum boundary."""
        range_dict = {'min': 1000.0, 'max': 1020.0}
        assert self.matcher._is_in_range(1000.0, range_dict) is True
    
    def test_value_at_max_boundary(self):
        """Test value at maximum boundary."""
        range_dict = {'min': 1000.0, 'max': 1020.0}
        assert self.matcher._is_in_range(1020.0, range_dict) is True
    
    def test_only_min_specified(self):
        """Test range with only minimum value."""
        range_dict = {'min': 1000.0}
        assert self.matcher._is_in_range(1010.0, range_dict) is True
        assert self.matcher._is_in_range(990.0, range_dict) is False
    
    def test_only_max_specified(self):
        """Test range with only maximum value."""
        range_dict = {'max': 1020.0}
        assert self.matcher._is_in_range(1010.0, range_dict) is True
        assert self.matcher._is_in_range(1030.0, range_dict) is False


class TestLocationMatching:
    """Test complete location matching with all components."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.matcher = LocationProfileMatcher()
    
    def test_no_location_profile_returns_none(self):
        """Test that missing location profile returns None."""
        captured_data = {
            'latitude': 40.7128,
            'longitude': -74.0060
        }
        
        result = self.matcher.match_location(captured_data, None)
        assert result is None
    
    def test_perfect_match_all_components(self):
        """Test perfect match across all components."""
        # Mock location profile
        profile = Mock()
        profile.expected_latitude = 40.7128
        profile.expected_longitude = -74.0060
        profile.expected_wifi_bssids = ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:03"]
        profile.expected_cell_tower_ids = ["tower_001", "tower_002"]
        profile.expected_pressure_range = {'min': 1010.0, 'max': 1020.0}
        profile.expected_light_range = {'min': 100.0, 'max': 500.0}
        
        captured_data = {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'wifi_bssids': ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:03"],
            'cell_tower_ids': ["tower_001", "tower_002"],
            'pressure': 1015.0,
            'light_level': 300.0
        }
        
        result = self.matcher.match_location(captured_data, profile)
        
        assert result is not None
        assert result['match_score'] == 100.0
        assert result['distance_meters'] == 0.0
        assert result['details']['gps_score'] == 40.0
        assert result['details']['wifi_score'] == 30.0
        assert result['details']['cell_tower_score'] == 20.0
        assert result['details']['environmental_score'] == 10.0
    
    def test_partial_match(self):
        """Test partial match with some mismatches."""
        profile = Mock()
        profile.expected_latitude = 40.7128
        profile.expected_longitude = -74.0060
        profile.expected_wifi_bssids = ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:03"]
        profile.expected_cell_tower_ids = ["tower_001", "tower_002"]
        profile.expected_pressure_range = {'min': 1010.0, 'max': 1020.0}
        profile.expected_light_range = {'min': 100.0, 'max': 500.0}
        
        # Captured data with some differences
        captured_data = {
            'latitude': 40.7173,  # ~500m away
            'longitude': -74.0060,
            'wifi_bssids': ["AA:BB:CC:DD:EE:01"],  # Only 1 match
            'cell_tower_ids': ["tower_001"],  # Only 1 match
            'pressure': 1015.0,  # Matches
            'light_level': 600.0  # Out of range
        }
        
        result = self.matcher.match_location(captured_data, profile)
        
        assert result is not None
        assert 0 < result['match_score'] < 100.0
        assert result['distance_meters'] > 0
        assert result['details']['wifi_matches'] == 1
        assert result['details']['cell_tower_matches'] == 1
        assert result['details']['pressure_match'] is True
        assert result['details']['light_match'] is False
    
    def test_missing_optional_sensors(self):
        """Test matching with missing optional sensor data."""
        profile = Mock()
        profile.expected_latitude = 40.7128
        profile.expected_longitude = -74.0060
        profile.expected_wifi_bssids = None
        profile.expected_cell_tower_ids = None
        profile.expected_pressure_range = None
        profile.expected_light_range = None
        
        captured_data = {
            'latitude': 40.7128,
            'longitude': -74.0060
        }
        
        result = self.matcher.match_location(captured_data, profile)
        
        assert result is not None
        # Only GPS score should be calculated
        assert result['match_score'] == 40.0
        assert result['details']['wifi_score'] == 0.0
        assert result['details']['cell_tower_score'] == 0.0
        assert result['details']['environmental_score'] == 0.0
    
    def test_gps_only_match(self):
        """Test matching with GPS data only."""
        profile = Mock()
        profile.expected_latitude = 40.7128
        profile.expected_longitude = -74.0060
        profile.expected_wifi_bssids = []
        profile.expected_cell_tower_ids = []
        profile.expected_pressure_range = None
        profile.expected_light_range = None
        
        captured_data = {
            'latitude': 40.7140,  # Close but not exact
            'longitude': -74.0060
        }
        
        result = self.matcher.match_location(captured_data, profile)
        
        assert result is not None
        assert result['distance_meters'] > 0
        assert result['distance_meters'] < 200  # Should be close
        assert result['match_score'] > 0
        assert result['match_score'] == result['details']['gps_score']
    
    def test_poor_match_all_components(self):
        """Test poor match across all components."""
        profile = Mock()
        profile.expected_latitude = 40.7128
        profile.expected_longitude = -74.0060
        profile.expected_wifi_bssids = ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]
        profile.expected_cell_tower_ids = ["tower_001", "tower_002"]
        profile.expected_pressure_range = {'min': 1010.0, 'max': 1020.0}
        profile.expected_light_range = {'min': 100.0, 'max': 500.0}
        
        # Captured data with no matches
        captured_data = {
            'latitude': 41.0,  # Far away
            'longitude': -75.0,
            'wifi_bssids': ["FF:FF:FF:FF:FF:01"],  # No matches
            'cell_tower_ids': ["tower_999"],  # No matches
            'pressure': 900.0,  # Out of range
            'light_level': 1000.0  # Out of range
        }
        
        result = self.matcher.match_location(captured_data, profile)
        
        assert result is not None
        assert result['match_score'] == 0.0
        assert result['distance_meters'] > 10000  # Very far
        assert result['details']['wifi_matches'] == 0
        assert result['details']['cell_tower_matches'] == 0
        assert result['details']['pressure_match'] is False
        assert result['details']['light_match'] is False
    
    def test_missing_gps_coordinates(self):
        """Test handling of missing GPS coordinates."""
        profile = Mock()
        profile.expected_latitude = 40.7128
        profile.expected_longitude = -74.0060
        profile.expected_wifi_bssids = ["AA:BB:CC:DD:EE:01"]
        profile.expected_cell_tower_ids = None
        profile.expected_pressure_range = None
        profile.expected_light_range = None
        
        captured_data = {
            'wifi_bssids': ["AA:BB:CC:DD:EE:01"]
        }
        
        result = self.matcher.match_location(captured_data, profile)
        
        assert result is not None
        assert result['distance_meters'] == 0.0
        assert result['details']['gps_score'] == 0.0
        # WiFi score should still be calculated
        assert result['details']['wifi_score'] > 0


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.matcher = LocationProfileMatcher()
    
    def test_empty_captured_data(self):
        """Test with empty captured data."""
        profile = Mock()
        profile.expected_latitude = 40.7128
        profile.expected_longitude = -74.0060
        profile.expected_wifi_bssids = []
        profile.expected_cell_tower_ids = []
        profile.expected_pressure_range = None
        profile.expected_light_range = None
        
        result = self.matcher.match_location({}, profile)
        
        assert result is not None
        assert result['match_score'] == 0.0
    
    def test_empty_wifi_lists(self):
        """Test with empty WiFi BSSID lists."""
        captured = []
        expected = []
        
        matches = self.matcher._count_wifi_matches(captured, expected)
        assert matches == 0
    
    def test_empty_cell_tower_lists(self):
        """Test with empty cell tower ID lists."""
        captured = []
        expected = []
        
        matches = self.matcher._count_cell_tower_matches(captured, expected)
        assert matches == 0
    
    def test_extreme_gps_coordinates(self):
        """Test with extreme GPS coordinates."""
        # North pole to south pole
        distance = self.matcher.calculate_haversine_distance(
            90.0, 0.0,
            -90.0, 0.0
        )
        # Should be approximately half Earth's circumference
        assert 19900000 < distance < 20100000
