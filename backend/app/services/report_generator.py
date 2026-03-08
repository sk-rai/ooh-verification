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
        map_generator: MapGenerator
    ):
        self.db = db
        self.chart_generator = chart_generator
        self.map_generator = map_generator

    async def generate_csv_report(self, campaign_code: str) -> str:
        """Generate CSV report for a campaign."""
        query = (
            select(Photo, SensorData, AuditLog)
            .join(SensorData, Photo.photo_id == SensorData.photo_id)
            .outerjoin(AuditLog, Photo.photo_id == AuditLog.photo_id)
            .where(Photo.campaign_code == campaign_code)
            .order_by(Photo.timestamp.desc())
        )
        
        result = await self.db.execute(query)
        rows = result.all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'Photo ID', 'Timestamp', 'Vendor ID', 'Verification Status',
            'Match Confidence', 'GPS Latitude', 'GPS Longitude', 'GPS Accuracy (m)',
            'WiFi Networks Count', 'Cell Towers Count', 'Audit Flags', 'S3 URL'
        ])
        
        for photo, sensor_data, audit_log in rows:
            writer.writerow([
                str(photo.photo_id),
                photo.timestamp.isoformat() if photo.timestamp else '',
                photo.vendor_id,
                photo.verification_status.value if photo.verification_status else '',
                photo.match_confidence if photo.match_confidence is not None else '',
                sensor_data.gps_latitude if sensor_data else '',
                sensor_data.gps_longitude if sensor_data else '',
                sensor_data.gps_accuracy if sensor_data else '',
                len(sensor_data.wifi_bssids) if sensor_data and sensor_data.wifi_bssids else 0,
                len(sensor_data.cell_tower_ids) if sensor_data and sensor_data.cell_tower_ids else 0,
                ','.join(audit_log.audit_flags) if audit_log and audit_log.audit_flags else '',
                photo.s3_url if photo.s3_url else ''
            ])
        
        return output.getvalue()

    async def generate_geojson_report(self, campaign_code: str) -> Dict[str, Any]:
        """Generate GeoJSON report for a campaign."""
        query = (
            select(Photo, SensorData, AuditLog)
            .join(SensorData, Photo.photo_id == SensorData.photo_id)
            .outerjoin(AuditLog, Photo.photo_id == AuditLog.photo_id)
            .where(Photo.campaign_code == campaign_code)
        )
        
        result = await self.db.execute(query)
        rows = result.all()
        
        photos = []
        for photo, sensor_data, audit_log in rows:
            photos.append({
                'photo_id': photo.photo_id,
                'latitude': sensor_data.gps_latitude,
                'longitude': sensor_data.gps_longitude,
                'timestamp': photo.timestamp,
                'verification_status': photo.verification_status.value if photo.verification_status else 'unknown',
                'match_confidence': photo.match_confidence,
                'vendor_id': photo.vendor_id,
                's3_url': photo.s3_url,
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
            .where(Photo.campaign_code == campaign_code)
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
            
            if photo.match_confidence is not None:
                confidence_scores.append(photo.match_confidence)
            
            if audit_log and audit_log.audit_flags:
                for flag in audit_log.audit_flags:
                    audit_flag_counts[flag] += 1
            
            vendor_counts[photo.vendor_id] += 1
            
            if photo.timestamp:
                timestamps.append(photo.timestamp)
        
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
                'timestamps': timestamps
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
