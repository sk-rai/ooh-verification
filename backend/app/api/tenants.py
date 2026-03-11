"""
Tenant Management API endpoints.

Provides tenant CRUD operations for administrators and branding retrieval for public access.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.models.tenant_config import TenantConfig
from app.schemas.tenant import (
    TenantCreate, TenantUpdate, TenantResponse, TenantListResponse, BrandingResponse
)
from app.middleware.tenant_context import get_current_tenant

router = APIRouter(prefix="/api", tags=["tenants"])


@router.post("/admin/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    data: TenantCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new tenant configuration.
    
    Requirements:
        - Req 1.1: Tenant configuration storage
        - Req 1.2: Tenant identification via subdomain/custom domain
        - Admin only endpoint (TODO: Add admin authentication)
    
    Note: This endpoint should be protected with admin authentication in production.
    """
    # Check if subdomain already exists
    result = await db.execute(
        select(TenantConfig).where(TenantConfig.subdomain == data.subdomain)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subdomain '{data.subdomain}' already exists"
        )
    
    # Check if custom domain already exists (if provided)
    if data.custom_domain:
        result = await db.execute(
            select(TenantConfig).where(TenantConfig.custom_domain == data.custom_domain)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Custom domain '{data.custom_domain}' already exists"
            )
    
    # Create tenant
    tenant = TenantConfig(
        tenant_name=data.tenant_name,
        subdomain=data.subdomain,
        custom_domain=data.custom_domain,
        logo_url=data.logo_url,
        primary_color=data.primary_color or '#3B82F6',
        secondary_color=data.secondary_color or '#10B981',
        email_from_name=data.email_from_name,
        email_from_address=data.email_from_address,
        email_templates=data.email_templates,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    
    return tenant


@router.get("/admin/tenants", response_model=TenantListResponse)
async def list_tenants(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db)
):
    """
    List all tenants.
    
    Requirements:
        - Req 1.1: Tenant listing
        - Admin only endpoint (TODO: Add admin authentication)
    
    Note: This endpoint should be protected with admin authentication in production.
    """
    # Build query
    query = select(TenantConfig)
    
    # Apply active filter if provided
    if is_active is not None:
        query = query.where(TenantConfig.is_active == is_active)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination and ordering
    query = query.order_by(TenantConfig.created_at.desc()).offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    tenants = result.scalars().all()
    
    return TenantListResponse(tenants=tenants, total=total)


@router.get("/admin/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get tenant details by ID.
    
    Requirements:
        - Req 1.1: Tenant retrieval
        - Admin only endpoint (TODO: Add admin authentication)
    """
    result = await db.execute(
        select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return tenant


@router.put("/admin/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID,
    data: TenantUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update tenant configuration.
    
    Requirements:
        - Req 1.2: Tenant configuration updates
        - Req 2.1: Branding configuration updates
        - Admin only endpoint (TODO: Add admin authentication)
    """
    # Get tenant
    result = await db.execute(
        select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check subdomain uniqueness if being updated
    if data.subdomain and data.subdomain != tenant.subdomain:
        result = await db.execute(
            select(TenantConfig).where(
                TenantConfig.subdomain == data.subdomain,
                TenantConfig.tenant_id != tenant_id
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subdomain '{data.subdomain}' already exists"
            )
    
    # Check custom domain uniqueness if being updated
    if data.custom_domain and data.custom_domain != tenant.custom_domain:
        result = await db.execute(
            select(TenantConfig).where(
                TenantConfig.custom_domain == data.custom_domain,
                TenantConfig.tenant_id != tenant_id
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Custom domain '{data.custom_domain}' already exists"
            )
    
    # Update fields if provided
    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)
    
    tenant.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(tenant)
    
    # TODO: Invalidate Redis cache for this tenant's branding
    
    return tenant


@router.delete("/admin/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Soft delete a tenant (set is_active=false).
    
    Requirements:
        - Req 1.3: Tenant deactivation
        - Admin only endpoint (TODO: Add admin authentication)
    
    Note: This is a soft delete. The tenant record remains in the database but is marked inactive.
    """
    # Get tenant
    result = await db.execute(
        select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Soft delete
    tenant.is_active = False
    tenant.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return None


@router.get("/branding", response_model=BrandingResponse)
async def get_branding(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Get tenant branding configuration (public endpoint, no authentication required).
    
    Requirements:
        - Req 2.1: Branding retrieval
        - Req 2.2: Public access to branding
        - Req 2.3: Caching support (TODO: Add Redis caching)
    
    This endpoint is used by the frontend to load tenant-specific branding
    based on the current hostname (subdomain or custom domain).
    
    The tenant is resolved from:
    1. X-Tenant-ID header
    2. Custom domain
    3. Subdomain
    4. Default tenant
    """
    try:
        tenant_id = get_current_tenant(request)
    except:
        # If tenant resolution fails, return default branding
        tenant_id = None
    
    if not tenant_id:
        # Return default branding
        return BrandingResponse(
            tenant_name="TrustCapture",
            logo_url=None,
            primary_color="#3B82F6",
            secondary_color="#10B981"
        )
    
    # Get tenant branding
    result = await db.execute(
        select(TenantConfig).where(
            TenantConfig.tenant_id == tenant_id,
            TenantConfig.is_active == True
        )
    )
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        # Return default branding if tenant not found
        return BrandingResponse(
            tenant_name="TrustCapture",
            logo_url=None,
            primary_color="#3B82F6",
            secondary_color="#10B981"
        )
    
    # TODO: Cache this response in Redis with 5-minute TTL
    
    return BrandingResponse(
        tenant_name=tenant.tenant_name,
        logo_url=tenant.logo_url,
        primary_color=tenant.primary_color,
        secondary_color=tenant.secondary_color
    )
