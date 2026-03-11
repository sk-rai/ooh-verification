"""
Subscription model - tracks client subscription details and usage.
Supports both Razorpay (India) and Stripe (International) payment gateways.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base
from app.models.client import SubscriptionTier, SubscriptionStatus


class Subscription(Base):
    """
    Subscription model - manages client subscription and usage tracking.

    Requirements:
    - Req 11.1: Subscription tiers (Free, Pro, Enterprise)
    - Req 11.2: Payment integration (Razorpay for India, Stripe for international)
    - Req 11.3: Usage tracking (photos, vendors, campaigns, storage)
    - Req 11.4: Quota enforcement
    """
    __tablename__ = "subscriptions"

    # Primary Key
    subscription_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Multi-tenancy
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Client Association
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.client_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One subscription per client
        index=True
    )

    # Subscription Details
    tier = Column(
        SQLEnum(SubscriptionTier, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SubscriptionTier.FREE
    )
    status = Column(
        SQLEnum(SubscriptionStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SubscriptionStatus.ACTIVE
    )

    # Payment Gateway Integration (Razorpay or Stripe)
    payment_gateway = Column(String(20), nullable=True)  # 'razorpay' or 'stripe'
    gateway_subscription_id = Column(String(255), nullable=True, unique=True)  # Gateway's subscription ID
    gateway_customer_id = Column(String(255), nullable=True)  # Gateway's customer ID

    # Legacy Stripe field (for backward compatibility)
    stripe_subscription_id = Column(String(255), nullable=True, unique=True)

    # Billing Details
    billing_cycle = Column(String(20), nullable=False, default='monthly')  # 'monthly' or 'yearly'
    amount = Column(Integer, nullable=False, default=0)  # Amount in smallest currency unit (paise/cents)
    currency = Column(String(3), nullable=False, default='INR')  # 'INR' or 'USD'
    auto_renew = Column(Integer, nullable=False, default=1)  # Boolean: 1=true, 0=false

    # Billing Period
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    trial_end_date = Column(DateTime, nullable=True)
    cancellation_date = Column(DateTime, nullable=True)

    # Usage Quotas
    photos_quota = Column(Integer, nullable=False)  # Monthly photo limit
    photos_used = Column(Integer, nullable=False, default=0)  # Photos used this period
    vendors_quota = Column(Integer, nullable=False)  # Max vendors allowed
    vendors_used = Column(Integer, nullable=False, default=0)  # Current vendor count
    campaigns_quota = Column(Integer, nullable=False)  # Max campaigns allowed
    campaigns_used = Column(Integer, nullable=False, default=0)  # Current campaign count
    storage_quota_mb = Column(Integer, nullable=False)  # Storage limit in MB
    storage_used_mb = Column(Integer, nullable=False, default=0)  # Storage used in MB

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    client = relationship("Client", back_populates="subscription")

    def __repr__(self):
        return (
            f"<Subscription(subscription_id={self.subscription_id}, "
            f"tier={self.tier}, status={self.status}, "
            f"usage={self.photos_used}/{self.photos_quota})>"
        )

    @property
    def has_photo_quota_remaining(self) -> bool:
        """Check if client has remaining photo quota."""
        if self.tier == SubscriptionTier.ENTERPRISE:
            return True  # Unlimited
        return self.photos_used < self.photos_quota

    @property
    def has_vendor_quota_remaining(self) -> bool:
        """Check if client can create more vendors."""
        if self.tier == SubscriptionTier.ENTERPRISE:
            return True  # Unlimited
        return self.vendors_used < self.vendors_quota

    @property
    def has_campaign_quota_remaining(self) -> bool:
        """Check if client can create more campaigns."""
        if self.tier == SubscriptionTier.ENTERPRISE:
            return True  # Unlimited
        return self.campaigns_used < self.campaigns_quota

    @property
    def has_storage_quota_remaining(self) -> bool:
        """Check if client has remaining storage quota."""
        return self.storage_used_mb < self.storage_quota_mb

    def can_upload_photo(self, file_size_mb: float) -> bool:
        """Check if client can upload a photo of given size."""
        if not self.has_photo_quota_remaining:
            return False
        if self.storage_used_mb + file_size_mb > self.storage_quota_mb:
            return False
        return True

    @property
    def quota_percentage_used(self) -> float:
        """Calculate percentage of photo quota used."""
        if self.tier == SubscriptionTier.ENTERPRISE:
            return 0.0  # Unlimited
        if self.photos_quota == 0:
            return 100.0
        return (self.photos_used / self.photos_quota) * 100

    @property
    def storage_percentage_used(self) -> float:
        """Calculate percentage of storage quota used."""
        if self.storage_quota_mb == 0:
            return 100.0
        return (self.storage_used_mb / self.storage_quota_mb) * 100

    def get_usage_stats(self) -> dict:
        """Get comprehensive usage statistics."""
        return {
            "photos": {
                "used": self.photos_used,
                "quota": self.photos_quota if self.tier != SubscriptionTier.ENTERPRISE else "unlimited",
                "percentage": self.quota_percentage_used
            },
            "vendors": {
                "used": self.vendors_used,
                "quota": self.vendors_quota if self.tier != SubscriptionTier.ENTERPRISE else "unlimited"
            },
            "campaigns": {
                "used": self.campaigns_used,
                "quota": self.campaigns_quota if self.tier != SubscriptionTier.ENTERPRISE else "unlimited"
            },
            "storage": {
                "used_mb": self.storage_used_mb,
                "quota_mb": self.storage_quota_mb,
                "percentage": self.storage_percentage_used
            }
        }
