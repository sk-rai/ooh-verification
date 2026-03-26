"""Schemas for admin API."""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class AdminLogin(BaseModel):
    email: str = Field(..., description="Admin email")
    password: str = Field(..., description="Admin password")


class AdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminUserResponse(BaseModel):
    admin_id: UUID
    email: str
    name: str
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Dashboard Metrics ----

class TierBreakdown(BaseModel):
    free: int = 0
    pro: int = 0
    enterprise: int = 0


class SubscriptionBreakdown(BaseModel):
    active: int = 0
    cancelled: int = 0
    expired: int = 0
    past_due: int = 0


class SignupTrend(BaseModel):
    date: str
    count: int


class TopClient(BaseModel):
    client_id: str
    company_name: str
    email: str
    tier: str
    vendors_count: int
    campaigns_count: int
    last_active: Optional[str] = None


class PlatformOverview(BaseModel):
    total_tenants: int
    total_clients: int
    total_vendors: int
    total_campaigns: int
    total_assignments: int
    total_photos: int


class ClientMetrics(BaseModel):
    total: int
    tier_breakdown: TierBreakdown
    subscription_breakdown: SubscriptionBreakdown
    signups_last_7_days: int
    signups_last_30_days: int
    signup_trend: List[SignupTrend]


class UsageMetrics(BaseModel):
    heavy_users: List[TopClient]
    light_users: List[TopClient]
    inactive_users: List[TopClient]
    recently_active: List[TopClient]


class RevenueMetrics(BaseModel):
    total_revenue_inr: int = 0  # in paise
    total_revenue_usd: int = 0  # in cents
    total_gst_collected: int = 0  # in paise
    pending_refunds: int = 0  # count
    pending_refund_amount: int = 0  # in paise
    mrr_inr: int = 0  # monthly recurring revenue in paise
    paying_customers: int = 0


class PhotoStats(BaseModel):
    total: int = 0
    verified: int = 0
    flagged: int = 0
    rejected: int = 0
    pending: int = 0
    total_storage_mb: int = 0


class AdminDashboardResponse(BaseModel):
    overview: PlatformOverview
    clients: ClientMetrics
    usage: UsageMetrics
    revenue: RevenueMetrics
    photos: PhotoStats
