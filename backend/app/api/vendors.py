"""
Vendor Management API endpoints.

Provides vendor CRUD operations for clients to manage their field workers.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_active_client
from app.core.security import generate_vendor_id
from app.core.sms import sms_service
from app.models import Client, Vendor
from app.models.vendor_client_association import VendorClientAssociation, AssociationStatus
from app.models.vendor import VendorStatus
from app.schemas.vendor import (
    VendorCreate, VendorUpdate, VendorResponse, VendorListResponse
)
from app.services.quota_enforcer import get_quota_enforcer, QuotaExceededError

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


@router.post("", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    data: VendorCreate,
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new vendor with auto-generated ID and send welcome SMS.
    
    Requirements:
        - Req 1.1: Vendor creation by clients
        - Req 1.2: Vendor ID generation (6-char alphanumeric)
        - Req 1.3: SMS delivery with vendor ID and app download link
        - Req 11.4: Quota enforcement
    """
    # Check vendor quota
    enforcer = get_quota_enforcer(db)
    try:
        await enforcer.check_vendor_quota(str(client.client_id))
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=e.to_dict()
        )
    
    # Generate unique vendor ID
    max_attempts = 10
    vendor_id = None
    
    for _ in range(max_attempts):
        candidate_id = generate_vendor_id()
        
        # Check if ID already exists
        result = await db.execute(
            select(Vendor).where(Vendor.vendor_id == candidate_id)
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            vendor_id = candidate_id
            break
    
    if not vendor_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate unique vendor ID"
        )
    
    # Create vendor
    vendor = Vendor(
        vendor_id=vendor_id,
        tenant_id=client.tenant_id,
        name=data.name,
        phone_number=data.phone_number,
        email=data.email,
        city=getattr(data, 'city', None),
        state=getattr(data, 'state', None),
        country=getattr(data, 'country', None),
        created_by_client_id=client.client_id
    )
    
    db.add(vendor)
    await db.commit()
    await db.refresh(vendor)
    
    # Increment vendor usage counter (Req 11.3: Usage tracking)
    try:
        await enforcer.increment_vendor_usage(str(client.client_id))
    except Exception as e:
        # Log error but don't fail since vendor is already created
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to increment vendor usage: {str(e)}")
    
    # Send welcome SMS with vendor ID and app download link
    await sms_service.send_vendor_welcome_sms(
        phone_number=data.phone_number,
        vendor_id=vendor_id,
        vendor_name=data.name
    )
    
    return vendor


@router.get("", response_model=VendorListResponse)
async def list_vendors(
    status_filter: Optional[str] = Query(None, description="Filter by status (active/inactive)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    List all vendors for the authenticated client.
    
    Supports filtering by status and pagination.
    
    Requirements:
        - Req 1.1: Vendor listing for clients
        - Authorization: Clients can only see their own vendors
    """
    # Build query
    query = select(Vendor).join(
        VendorClientAssociation,
        Vendor.vendor_id == VendorClientAssociation.vendor_id
    ).where(
        VendorClientAssociation.client_id == client.client_id,
        VendorClientAssociation.status == AssociationStatus.ACTIVE
    )
    
    # Apply status filter if provided
    if status_filter:
        try:
            status_enum = VendorStatus(status_filter.lower())
            query = query.where(Vendor.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}. Must be 'active' or 'inactive'"
            )
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination and ordering
    query = query.order_by(Vendor.created_at.desc()).offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    vendors = result.scalars().all()
    
    return VendorListResponse(vendors=vendors, total=total)


@router.patch("/{vendor_id}", response_model=VendorResponse)
async def update_vendor(
    vendor_id: str,
    data: VendorUpdate,
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Update vendor information.
    
    Requirements:
        - Req 1.2: Vendor information updates
        - Authorization: Clients can only update their own vendors
    """
    # Get vendor
    result = await db.execute(
        select(Vendor).join(
            VendorClientAssociation,
            Vendor.vendor_id == VendorClientAssociation.vendor_id
        ).where(
            Vendor.vendor_id == vendor_id,
            VendorClientAssociation.client_id == client.client_id,
            VendorClientAssociation.status == AssociationStatus.ACTIVE
        )
    )
    vendor = result.scalar_one_or_none()
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )
    
    # Update fields if provided
    if data.name is not None:
        vendor.name = data.name
    if data.phone_number is not None:
        vendor.phone_number = data.phone_number
    if data.email is not None:
        vendor.email = data.email
    
    vendor.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(vendor)
    
    return vendor


@router.patch("/{vendor_id}/deactivate", response_model=VendorResponse)
async def deactivate_vendor(
    vendor_id: str,
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Deactivate a vendor (soft delete).
    
    Requirements:
        - Req 1.3: Vendor deactivation
        - Authorization: Clients can only deactivate their own vendors
    """
    # Get vendor
    result = await db.execute(
        select(Vendor).join(
            VendorClientAssociation,
            Vendor.vendor_id == VendorClientAssociation.vendor_id
        ).where(
            Vendor.vendor_id == vendor_id,
            VendorClientAssociation.client_id == client.client_id,
            VendorClientAssociation.status == AssociationStatus.ACTIVE
        )
    )
    vendor = result.scalar_one_or_none()
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )
    
    # Deactivate vendor
    vendor.status = VendorStatus.INACTIVE
    vendor.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(vendor)
    
    # Decrement vendor usage counter (Req 11.3: Usage tracking)
    try:
        enforcer = get_quota_enforcer(db)
        await enforcer.decrement_vendor_usage(str(client.client_id))
    except Exception as e:
        # Log error but don't fail since vendor is already deactivated
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to decrement vendor usage: {str(e)}")
    
    return vendor
