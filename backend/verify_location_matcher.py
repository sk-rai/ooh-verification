#!/usr/bin/env python3
"""
Simple verification script for location profile matcher.
"""

import sys
sys.path.insert(0, '/home/lynksavvy/projects/trustcapture/backend')

from app.services.location_profile_matcher import LocationProfileMatcher
from unittest.mock import Mock

def test_basic_functionality():
    """Test basic functionality of location matcher."""
    matcher = LocationProfileMatcher()
    
    # Test 1: Haversine distance calculation
    print("Test 1: Haversine distance (same location)")
    distance = matcher.calculate_haversine_distance(40.7128, -74.0060, 40.7128, -74.0060)
    print(f"  Distance: {distance}m (expected: 0)")
    assert distance == 0.0, "Same location should have 0 distance"
    print("  ✓ PASSED")
    
    # Test 2: GPS scoring
    print("\nTest 2: GPS scoring")
    score = matcher._calculate_gps_score(25.0)
    print(f"  Score for 25m: {score} (expected: {matcher.GPS_WEIGHT})")
    assert score == matcher.GPS_WEIGHT, "Excellent distance should get full score"
    print("  ✓ PASSED")
    
    # Test 3: WiFi matching
    print("\nTest 3: WiFi matching")
    captured = ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:03"]
    expected = ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:03"]
    matches = matcher._count_wifi_matches(captured, expected)
    print(f"  Matches: {matches} (expected: 3)")
    assert matches == 3, "Should match all 3 BSSIDs"
    print("  ✓ PASSED")
    
    # Test 4: No location profile returns None
    print("\nTest 4: No location profile")
    result = matcher.match_location({'latitude': 40.7128, 'longitude': -74.0060}, None)
    print(f"  Result: {result} (expected: None)")
    assert result is None, "Should return None when no profile"
    print("  ✓ PASSED")
    
    # Test 5: Perfect match
    print("\nTest 5: Perfect match")
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
    
    result = matcher.match_location(captured_data, profile)
    print(f"  Match score: {result['match_score']} (expected: 100.0)")
    print(f"  Distance: {result['distance_meters']}m (expected: 0.0)")
    assert result['match_score'] == 100.0, "Perfect match should score 100"
    assert result['distance_meters'] == 0.0, "Same location should have 0 distance"
    print("  ✓ PASSED")
    
    print("\n" + "="*50)
    print("All tests passed! ✓")
    print("="*50)

if __name__ == "__main__":
    try:
        test_basic_functionality()
    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
