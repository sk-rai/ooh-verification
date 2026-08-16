"""
VendorTrack model — stores daily GPS track for vendor field activity.

One record per vendor per day. Points are stored as JSONB array.
Used for attendance proof and route visualization.
"""
from sqlalchemy import Column, String, Float, Integer, DateTime, Date, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

from app.core.database import Base


class VendorTrack(Base):
    """Daily GPS track for a vendor. One row per vendor per day."""
    __tablename__ = "vendor_tracks"

    __table_args__ = (
        UniqueConstraint('vendor_id', 'track_date', name='uq_vendor_track_date'),
    )

    track_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    vendor_id = Column(String(6), nullable=False, index=True)
    track_date = Column(Date, nullable=False, index=True)

    # GPS points array: [{lat, lon, accuracy, timestamp_ms, battery_pct}, ...]
    points = Column(JSONB, nullable=False, default=list)
    point_count = Column(Integer, nullable=False, default=0)

    # Computed stats
    total_distance_meters = Column(Float, nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Status
    status = Column(String(20), nullable=False, default="active")  # active, completed

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=__import__("datetime").timezone.utc), onupdate=lambda: datetime.now(tz=__import__("datetime").timezone.utc), nullable=False)

    def __repr__(self):
        return f"<VendorTrack(vendor={self.vendor_id}, date={self.track_date}, points={self.point_count})>"
