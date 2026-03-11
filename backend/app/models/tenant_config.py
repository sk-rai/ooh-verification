"""Tenant configuration model for multi-tenancy support."""
from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base
import uuid


class TenantConfig(Base):
    """Tenant configuration for white-label multi-tenancy."""
    __tablename__ = "tenant_config"

    tenant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_name = Column(String(255), nullable=False)
    subdomain = Column(String(100), unique=True, nullable=True, index=True)
    custom_domain = Column(String(255), unique=True, nullable=True, index=True)
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), nullable=True, default='#3B82F6')
    secondary_color = Column(String(7), nullable=True, default='#10B981')
    email_from_name = Column(String(255), nullable=True)
    email_from_address = Column(String(255), nullable=True)
    email_templates = Column(JSONB, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<TenantConfig(tenant_id={self.tenant_id}, tenant_name='{self.tenant_name}', subdomain='{self.subdomain}')>"
