"""Page view tracking model."""
from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, Date, Integer, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class PageView(Base):
    """Raw page view events — purged after 30 days."""
    __tablename__ = "page_views"

    id = Column(BigInteger, autoincrement=True, primary_key=True)
    visitor_hash = Column(String(64), nullable=False, index=True)
    session_id = Column(String(64), nullable=True)
    page = Column(String(500), nullable=False)
    referrer = Column(String(1000), nullable=True)
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    device_type = Column(String(20), nullable=True)
    browser = Column(String(50), nullable=True)
    os = Column(String(50), nullable=True)
    utm_source = Column(String(200), nullable=True)
    utm_medium = Column(String(200), nullable=True)
    utm_campaign = Column(String(200), nullable=True)
    is_registered_user = Column(Boolean, default=False)
    tenant_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class DailyAnalyticsSummary(Base):
    """Daily aggregated analytics — kept forever."""
    __tablename__ = "daily_analytics_summary"

    id = Column(BigInteger, autoincrement=True, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=True)
    total_views = Column(Integer, default=0)
    unique_visitors = Column(Integer, default=0)
    unique_sessions = Column(Integer, default=0)
    registered_views = Column(Integer, default=0)
    top_pages = Column(JSON, nullable=True)
    top_referrers = Column(JSON, nullable=True)
    countries = Column(JSON, nullable=True)
    devices = Column(JSON, nullable=True)
    browsers = Column(JSON, nullable=True)
    utm_sources = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('date', 'tenant_id', name='uq_daily_summary_date_tenant'),
    )
