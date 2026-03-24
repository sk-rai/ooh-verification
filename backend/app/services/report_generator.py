"""
Report generation service.
Generates CSV, GeoJSON, and analytics for campaigns.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import csv
import io
from collections import Counter

from app.models.photo import Photo
from app.models.sensor_data import SensorData
from app.models.audit_log import AuditLog
from app.models.campaign import Campaign
from app.services.chart_generator import ChartGenerator
from app.services.map_generator import MapGenerator


class ReportGenerator:
    """Generate reports for campaigns."""

    def __init__(
        self,
        db: AsyncSession,
        chart_generator: ChartGenerator,
        map_generator: MapGenerator,
        tenant_id=None
    ):
        self.db = db
        self.chart_generator = chart_generator
        self.map_generator = map_generator
        self.tenant_id = tenant_id

    async def generate_csv_report(self, campaign_code: str) -> str:
        """Generate CSV report for a campaign."""
        # First verify campaign exists
        campaign_query = select(Campaign).where(Campaign.campaign_code == campaign_code)
        campaign_result = await self.db.execute(campaign_query)
        campaign = campaign_result.scalar_one_or_none()
        
        if not campaign:
            raise ValueError(f"Campaign {campaign_code} not found")
        
        # Query photos with sensor data and audit logs
        query = (
            select(Photo, SensorData, AuditLog)
            .join(SensorData, Photo.photo_id == SensorData.photo_id)
            .outerjoin(AuditLog, Photo.photo_id == AuditLog.photo_id)
            .where(Photo.campaign_id == campaign.campaign_id)
            .order_by(Photo.capture_timestamp.desc())
        )
        
        result = await self.db.execute(query)
        rows = result.all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # CSV header with all required fields
        writer.writerow([
            'Photo ID', 'Capture Timestamp', 'Upload Timestamp', 'Vendor ID', 
            'Verification Status', 'Location Match Score', 'Distance From Expected (m)',
            'GPS Latitude', 'GPS Longitude', 'GPS Accuracy (m)', 'GPS Altitude (m)',
            'GPS Provider', 'GPS Satellites',
            'WiFi Networks Count', 'Cell Towers Count', 
            'Barometer Pressure (hPa)', 'Ambient Light (lux)',
            'Hand Tremor Detected', 'Confidence Score',
            'Audit Flags', 'S3 Key'
        ])
        
        for photo, sensor_data, audit_log in rows:
            # Format GPS coordinates with 7 decimal precision
            gps_lat = f"{sensor_data.gps_latitude:.7f}" if sensor_data and sensor_data.gps_latitude is not None else ''
            gps_lon = f"{sensor_data.gps_longitude:.7f}" if sensor_data and sensor_data.gps_longitude is not None else ''
            
            writer.writerow([
                str(photo.photo_id),
                photo.capture_timestamp.isoformat() if photo.capture_timestamp else '',
                photo.upload_timestamp.isoformat() if photo.upload_timestamp else '',
                photo.vendor_id,
                photo.verification_status.value if photo.verification_status else '',
                photo.location_match_score if photo.location_match_score is not None else '',
                photo.distance_from_expected if photo.distance_from_expected is not None else '',
                gps_lat,
                gps_lon,
                sensor_data.gps_accuracy if sensor_data and sensor_data.gps_accuracy is not None else '',
                sensor_data.gps_altitude if sensor_data and sensor_data.gps_altitude is not None else '',
                sensor_data.gps_provider if sensor_data else '',
                sensor_data.gps_satellite_count if sensor_data and sensor_data.gps_satellite_count is not None else '',
                len(sensor_data.wifi_networks) if sensor_data and sensor_data.wifi_networks else 0,
                len(sensor_data.cell_towers) if sensor_data and sensor_data.cell_towers else 0,
                sensor_data.barometer_pressure if sensor_data and sensor_data.barometer_pressure is not None else '',
                sensor_data.ambient_light_lux if sensor_data and sensor_data.ambient_light_lux is not None else '',
                'Yes' if sensor_data and sensor_data.hand_tremor_is_human else 'No' if sensor_data and sensor_data.hand_tremor_is_human is not None else '',
                sensor_data.confidence_score if sensor_data and sensor_data.confidence_score is not None else '',
                ','.join(audit_log.audit_flags) if audit_log and audit_log.audit_flags else '',
                photo.s3_key if photo.s3_key else ''
            ])
        
        return output.getvalue()

    async def generate_geojson_report(self, campaign_code: str) -> Dict[str, Any]:
        """Generate GeoJSON report for a campaign."""
        # First verify campaign exists
        campaign_query = select(Campaign).where(Campaign.campaign_code == campaign_code)
        campaign_result = await self.db.execute(campaign_query)
        campaign = campaign_result.scalar_one_or_none()
        
        if not campaign:
            raise ValueError(f"Campaign {campaign_code} not found")
        
        query = (
            select(Photo, SensorData, AuditLog)
            .join(SensorData, Photo.photo_id == SensorData.photo_id)
            .outerjoin(AuditLog, Photo.photo_id == AuditLog.photo_id)
            .where(Photo.campaign_id == campaign.campaign_id)
        )
        
        result = await self.db.execute(query)
        rows = result.all()
        
        photos = []
        for photo, sensor_data, audit_log in rows:
            photos.append({
                'photo_id': photo.photo_id,
                'latitude': sensor_data.gps_latitude,
                'longitude': sensor_data.gps_longitude,
                'timestamp': photo.capture_timestamp,
                'verification_status': photo.verification_status.value if photo.verification_status else 'unknown',
                'match_confidence': photo.location_match_score,
                'vendor_id': photo.vendor_id,
                's3_key': photo.s3_key,
                'gps_accuracy': sensor_data.gps_accuracy,
                'audit_flags': audit_log.audit_flags if audit_log else []
            })
        
        return self.map_generator.generate_geojson(photos)

    async def get_campaign_statistics(self, campaign_code: str) -> Dict[str, Any]:
        """Get statistics for a campaign."""
        campaign_query = select(Campaign).where(Campaign.campaign_code == campaign_code)
        campaign_result = await self.db.execute(campaign_query)
        campaign = campaign_result.scalar_one_or_none()
        
        if not campaign:
            raise ValueError(f"Campaign {campaign_code} not found")
        
        photos_query = (
            select(Photo, AuditLog)
            .outerjoin(AuditLog, Photo.photo_id == AuditLog.photo_id)
            .where(Photo.campaign_id == campaign.campaign_id)
        )
        photos_result = await self.db.execute(photos_query)
        photos_rows = photos_result.all()
        
        total_photos = len(photos_rows)
        status_counts = Counter()
        confidence_scores = []
        audit_flag_counts = Counter()
        vendor_counts = Counter()
        timestamps = []
        
        for photo, audit_log in photos_rows:
            status = photo.verification_status.value if photo.verification_status else 'unknown'
            status_counts[status] += 1
            
            if photo.location_match_score is not None:
                confidence_scores.append(photo.location_match_score)
            
            if audit_log and audit_log.audit_flags:
                for flag in audit_log.audit_flags:
                    audit_flag_counts[flag] += 1
            
            vendor_counts[photo.vendor_id] += 1
            
            if photo.capture_timestamp:
                timestamps.append(photo.capture_timestamp)
        
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        
        return {
            'campaign': {
                'code': campaign.campaign_code,
                'name': campaign.name,
                'type': campaign.campaign_type.value if campaign.campaign_type else None,
                'status': campaign.status.value if campaign.status else None
            },
            'statistics': {
                'total_photos': total_photos,
                'status_counts': dict(status_counts),
                'average_confidence': round(avg_confidence, 2),
                'flagged_photos': sum(1 for _, audit_log in photos_rows if audit_log and audit_log.audit_flags),
                'vendor_counts': dict(vendor_counts),
                'audit_flag_counts': dict(audit_flag_counts)
            },
            'raw_data': {
                'confidence_scores': confidence_scores,
                'timestamps': [ts.isoformat() if hasattr(ts, 'isoformat') else str(ts) for ts in timestamps]
            }
        }

    async def generate_chart_data(
        self,
        campaign_code: str,
        chart_type: str,
        format: str = 'json'
    ) -> Any:
        """Generate chart data for a campaign."""
        stats = await self.get_campaign_statistics(campaign_code)
        
        if chart_type == 'verification':
            return self.chart_generator.generate_verification_status_chart(
                stats['statistics']['status_counts'],
                format
            )
        elif chart_type == 'confidence':
            return self.chart_generator.generate_confidence_score_histogram(
                stats['raw_data']['confidence_scores'],
                format
            )
        elif chart_type == 'timeline':
            return self.chart_generator.generate_photos_over_time_chart(
                stats['raw_data']['timestamps'],
                format
            )
        else:
            raise ValueError(f"Unknown chart type: {chart_type}")
