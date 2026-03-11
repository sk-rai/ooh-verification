"""
Tenant context management for database queries.

This module provides utilities to automatically filter database queries by tenant_id.

Requirements: 1.3, 1.4
"""
from contextvars import ContextVar
from typing import Optional
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

# Context variable to store current tenant ID
_tenant_context: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)


def set_tenant_context(tenant_id: str) -> None:
    """
    Set the current tenant context.
    
    Args:
        tenant_id: UUID string of the tenant
    """
    _tenant_context.set(tenant_id)
    logger.debug(f"Tenant context set to: {tenant_id}")


def get_tenant_context() -> Optional[str]:
    """
    Get the current tenant context.
    
    Returns:
        tenant_id (UUID as string) or None if not set
    """
    return _tenant_context.get()


def clear_tenant_context() -> None:
    """Clear the tenant context."""
    _tenant_context.set(None)
    logger.debug("Tenant context cleared")


def require_tenant_context() -> str:
    """
    Get the current tenant context, raising an error if not set.
    
    Returns:
        tenant_id (UUID as string)
    
    Raises:
        RuntimeError: If tenant context is not set
    """
    tenant_id = get_tenant_context()
    if not tenant_id:
        raise RuntimeError("Tenant context not set. Ensure TenantContextMiddleware is enabled.")
    return tenant_id


class TenantContextManager:
    """
    Context manager for tenant-scoped operations.
    
    Usage:
        with TenantContextManager(tenant_id):
            # All database operations here will be scoped to tenant_id
            clients = db.query(Client).all()  # Automatically filtered by tenant_id
    """
    
    def __init__(self, tenant_id: str):
        """
        Initialize the context manager.
        
        Args:
            tenant_id: UUID string of the tenant
        """
        self.tenant_id = tenant_id
        self.previous_tenant_id = None
    
    def __enter__(self):
        """Enter the context."""
        self.previous_tenant_id = get_tenant_context()
        set_tenant_context(self.tenant_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context."""
        if self.previous_tenant_id:
            set_tenant_context(self.previous_tenant_id)
        else:
            clear_tenant_context()
        return False


def tenant_filter(model_class):
    """
    Helper function to create a tenant filter for SQLAlchemy queries.
    
    Usage:
        query = select(Client).where(tenant_filter(Client))
    
    Args:
        model_class: SQLAlchemy model class with tenant_id column
    
    Returns:
        SQLAlchemy filter expression
    """
    tenant_id = require_tenant_context()
    return model_class.tenant_id == tenant_id
