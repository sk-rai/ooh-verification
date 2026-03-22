#!/usr/bin/env python3
"""
Quick test to verify reports services work correctly.
"""
import asyncio
from datetime import datetime
from app.services.chart_generator import ChartGenerator
from app.services.map_generator import MapGenerator
import json


async def test_chart_generator():
    """Test chart generation."""
    print("Testing Chart Generator...")
    
    chart_gen = ChartGenerator()
    
    # Test verification status chart
    status_counts = {
        'verified': 45,
        'pending': 12,
        'flagged': 3,
        'rejected': 2
    }
    
    chart_json = chart_gen.generate_verification_status_chart(status_counts, format='json')
    chart_data = json.loads(chart_json)
    
    assert 'data' in chart_data
    assert 'layout' in chart_data
    print("✅ Verification status chart generated successfully")
    
    # Test confidence histogram
    confidence_scores = [85.5, 90.2, 78.3, 92.1, 88.7, 95.0, 82.4]
    chart_json = chart_gen.generate_confidence_score_histogram(confidence_scores, format='json')
    chart_data = json.loads(chart_json)
    
    assert 'data' in chart_data
    print("✅ Confidence histogram generated successfully")
    
    # Test timeline chart
    timestamps = [
        datetime(2026, 3, 1, 10, 0),
        datetime(2026, 3, 1, 14, 30),
        datetime(2026, 3, 2, 9, 15),
        datetime(2026, 3, 2, 16, 45),
        datetime(2026, 3, 3, 11, 20)
    ]
    chart_json = chart_gen.generate_photos_over_time_chart(timestamps, format='json')
    chart_data = json.loads(chart_json)
    
    assert 'data' in chart_data
    print("✅ Timeline chart generated successfully")


async def test_map_generator():
    """Test map generation."""
    print("\nTesting Map Generator...")
    
    map_gen = MapGenerator()
    
    # Test GeoJSON generation
    photos = [
        {
            'photo_id': '123e4567-e89b-12d3-a456-426614174000',
            'latitude': 12.9716,
            'longitude': 77.5946,
            'timestamp': datetime(2026, 3, 8, 10, 30),
            'verification_status': 'verified',
            'match_confidence': 92.5,
            'vendor_id': 'VND001',
            's3_url': 'https://s3.amazonaws.com/bucket/photo1.jpg',
            'gps_accuracy': 5.0,
            'audit_flags': []
        },
        {
            'photo_id': '223e4567-e89b-12d3-a456-426614174001',
            'latitude': 12.9726,
            'longitude': 77.5956,
            'timestamp': datetime(2026, 3, 8, 11, 45),
            'verification_status': 'pending',
            'match_confidence': 85.3,
            'vendor_id': 'VND001',
            's3_url': 'https://s3.amazonaws.com/bucket/photo2.jpg',
            'gps_accuracy': 8.0,
            'audit_flags': ['low_confidence']
        }
    ]
    
    geojson_data = map_gen.generate_geojson(photos)
    
    assert geojson_data['type'] == 'FeatureCollection'
    assert len(geojson_data['features']) == 2
    
    # Check first feature
    feature = geojson_data['features'][0]
    assert feature['type'] == 'Feature'
    assert feature['geometry']['type'] == 'Point'
    assert len(feature['geometry']['coordinates']) == 2
    assert feature['properties']['verification_status'] == 'verified'
    
    print("✅ GeoJSON generated successfully")
    print(f"   - {len(geojson_data['features'])} features created")
    print(f"   - First feature coordinates: {feature['geometry']['coordinates']}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Reports Services Quick Test")
    print("=" * 60)
    
    try:
        await test_chart_generator()
        await test_map_generator()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        print("\nReports services are working correctly.")
        print("Ready to test API endpoints with FastAPI server.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
