"""
Tenant context middleware for multi-tenancy support.

This middleware extracts the tenant identifier from:
1. Subdomain (e.g., client1.trustcapture.com)
2. Custom domain (e.g., client.com)
3. X-Tenant-ID header (for API clients)

Requirements: 1.2, 1.4
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.database import get_db
from app.models.tenant_config import TenantConfig

logger = logging.getLogger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to resolve and inject tenant context into requests.
    
    The tenant is resolved in the following order:
    1. X-Tenant-ID header (for API clients)
    2. Custom domain lookup
    3. Subdomain extraction
    
    Once resolved, the tenant_id is stored in request.state.tenant_id
    """
    
    # Paths that don't require tenant context
    EXCLUDED_PATHS = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api/admin/tenants",  # Admin endpoints
    ]
    
    async def dispatch(self, request: Request, call_next):
        """Process the request and inject tenant context."""
        
        # Skip tenant resolution for excluded paths
        if any(request.url.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return await call_next(request)
        
        try:
            tenant_id = await self._resolve_tenant(request)
            
            if not tenant_id:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "Tenant not found"}
                )
            
            # Store tenant_id in request state
            request.state.tenant_id = tenant_id
            
            logger.debug(f"Resolved tenant_id: {tenant_id} for path: {request.url.path}")
            
        except Exception as e:
            logger.error(f"Error resolving tenant: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Error resolving tenant context"}
            )
        
        response = await call_next(request)
        return response
    
    async def _resolve_tenant(self, request: Request) -> str:
        """
        Resolve tenant from request.
        
        Returns:
            tenant_id (UUID as string) or None if not found
        """
        # 1. Check X-Tenant-ID header
        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header:
            tenant = await self._get_tenant_by_id(tenant_header)
            if tenant and tenant.is_active:
                return str(tenant.tenant_id)
        
        # 2. Extract hostname
        hostname = request.url.hostname
        if not hostname:
            return None
        
        # 3. Check if it's a custom domain
        tenant = await self._get_tenant_by_custom_domain(hostname)
        if tenant and tenant.is_active:
            return str(tenant.tenant_id)
        
        # 4. Extract subdomain
        subdomain = self._extract_subdomain(hostname)
        if subdomain:
            tenant = await self._get_tenant_by_subdomain(subdomain)
            if tenant and tenant.is_active:
                return str(tenant.tenant_id)
        
        # 5. Default to 'default' tenant for development
        tenant = await self._get_tenant_by_subdomain("default")
        if tenant and tenant.is_active:
            return str(tenant.tenant_id)
        
        return None
    
    def _extract_subdomain(self, hostname: str) -> str:
        """
        Extract subdomain from hostname.
        
        Examples:
            client1.trustcapture.com -> client1
            trustcapture.com -> None
            localhost -> None
        """
        if hostname in ["localhost", "127.0.0.1"]:
            return "default"
        
        parts = hostname.split(".")
        if len(parts) >= 3:
            # Assume format: subdomain.domain.tld
            return parts[0]
        
        return None
    
    async def _get_tenant_by_id(self, tenant_id: str) -> TenantConfig:
        """Get tenant by ID."""
        async for db in get_db():
            result = await db.execute(
                select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
            )
            return result.scalar_one_or_none()
    
    async def _get_tenant_by_subdomain(self, subdomain: str) -> TenantConfig:
        """Get tenant by subdomain."""
        async for db in get_db():
            result = await db.execute(
                select(TenantConfig).where(TenantConfig.subdomain == subdomain)
            )
            return result.scalar_one_or_none()
    
    async def _get_tenant_by_custom_domain(self, domain: str) -> TenantConfig:
        """Get tenant by custom domain."""
        async for db in get_db():
            result = await db.execute(
                select(TenantConfig).where(TenantConfig.custom_domain == domain)
            )
            return result.scalar_one_or_none()


def get_current_tenant(request: Request) -> str:
    """
    Get the current tenant ID from request state.
    
    This function should be used in route handlers to access the tenant context.
    
    Args:
        request: FastAPI Request object
    
    Returns:
        tenant_id (UUID as string)
    
    Raises:
        HTTPException: If tenant context is not set
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context not available"
        )
    return tenant_id
