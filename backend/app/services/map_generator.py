"""
Map generation service.
Generates GeoJSON for web UI and static maps for PDFs.
"""
from typing import List, Dict, Any, Optional
import geojson
from datetime import datetime


class MapGenerator:
    """Generate maps for reports."""

    def __init__(self, mapbox_token: Optional[str] = None):
        """Initialize map generator."""
        self.mapbox_token = mapbox_token

    def generate_geojson(
        self,
        photos: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate GeoJSON FeatureCollection from photos.
        
        Args:
            photos: List of photo dicts with lat, lng, and metadata
                   
        Returns:
            GeoJSON FeatureCollection dict
        """
        features = []
        
        for photo in photos:
            point = geojson.Point((photo['longitude'], photo['latitude']))
            
            properties = {
                'photo_id': str(photo['photo_id']),
                'timestamp': photo['timestamp'].isoformat() if isinstance(photo['timestamp'], datetime) else photo['timestamp'],
                'verification_status': photo['verification_status'],
                'match_confidence': photo.get('match_confidence'),
                'vendor_id': photo['vendor_id'],
                's3_key': photo.get('s3_key'),
                'gps_accuracy': photo.get('gps_accuracy'),
                'audit_flags': photo.get('audit_flags', [])
            }
            
            feature = geojson.Feature(
                geometry=point,
                properties=properties,
                id=str(photo['photo_id'])
            )
            
            features.append(feature)
        
        feature_collection = geojson.FeatureCollection(features)
        
        return feature_collection
