"""
Client model - represents companies/organizations using TrustCapture.
"""
from sqlalchemy import Column, String, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class SubscriptionTier(str, enum.Enum):
    """Subscription tier enumeration."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    """Subscription status enumeration."""
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAST_DUE = "past_due"


class Client(Base):
    """
    Client model - companies that manage vendors and campaigns.
    
    Requirements:
    - Req 1.1: Client registration with email/password
    - Req 1.2: Subscription tier management
    """
    __tablename__ = "clients"

    # Primary Key
    client_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Authentication
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Company Information
    company_name = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=False)
    
    # Subscription
    subscription_tier = Column(
        SQLEnum(SubscriptionTier, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SubscriptionTier.FREE,
        index=True
    )
    subscription_status = Column(
        SQLEnum(SubscriptionStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
        index=True
    )
    
    # Stripe Integration
    stripe_customer_id = Column(String(255), nullable=True, unique=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    vendors = relationship("Vendor", back_populates="client", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="client", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="client", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Client(client_id={self.client_id}, email={self.email}, company={self.company_name})>"
