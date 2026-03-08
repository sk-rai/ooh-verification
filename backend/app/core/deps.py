"""
FastAPI dependencies for authentication and authorization.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import Client, Vendor
from app.schemas.auth import TokenData

# HTTP Bearer token security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> TokenData:
    """
    Dependency to get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer token from Authorization header
        db: Database session
        
    Returns:
        TokenData with user information
        
    Raises:
        HTTPException: If token is invalid or user not found
        
    Requirements:
        - Req 1.2: JWT token validation
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Decode token
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise credentials_exception
    
    # Extract user info from token
    user_id: str = payload.get("sub")
    user_type: str = payload.get("type")
    
    if user_id is None or user_type is None:
        raise credentials_exception
    
    # Create token data
    token_data = TokenData(
        user_id=user_id,
        user_type=user_type,
        email=payload.get("email"),
        vendor_id=payload.get("vendor_id")
    )
    
    return token_data


async def get_current_client(
    token_data: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Client:
    """
    Dependency to get current authenticated client.
    
    Args:
        token_data: Token data from get_current_user
        db: Database session
        
    Returns:
        Client model instance
        
    Raises:
        HTTPException: If user is not a client or client not found
        
    Requirements:
        - Req 1.1: Client authentication
    """
    if token_data.user_type != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized as client"
        )
    
    # Get client from database
    result = await db.execute(
        select(Client).where(Client.client_id == token_data.user_id)
    )
    client = result.scalar_one_or_none()
    
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    return client


async def get_current_vendor(
    token_data: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Vendor:
    """
    Dependency to get current authenticated vendor.
    
    Args:
        token_data: Token data from get_current_user
        db: Database session
        
    Returns:
        Vendor model instance
        
    Raises:
        HTTPException: If user is not a vendor or vendor not found
        
    Requirements:
        - Req 1.4: Vendor authentication
    """
    if token_data.user_type != "vendor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized as vendor"
        )
    
    # Get vendor from database
    result = await db.execute(
        select(Vendor).where(Vendor.vendor_id == token_data.vendor_id)
    )
    vendor = result.scalar_one_or_none()
    
    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )
    
    return vendor


async def get_current_active_client(
    client: Client = Depends(get_current_client)
) -> Client:
    """
    Dependency to get current active client (subscription active).
    
    Args:
        client: Client from get_current_client
        
    Returns:
        Client model instance
        
    Raises:
        HTTPException: If client subscription is not active
    """
    from app.models.client import SubscriptionStatus
    
    if client.subscription_status != SubscriptionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Client subscription is {client.subscription_status.value}"
        )
    
    return client


async def get_current_active_vendor(
    vendor: Vendor = Depends(get_current_vendor)
) -> Vendor:
    """
    Dependency to get current active vendor.
    
    Args:
        vendor: Vendor from get_current_vendor
        
    Returns:
        Vendor model instance
        
    Raises:
        HTTPException: If vendor is not active
    """
    from app.models.vendor import VendorStatus
    
    if vendor.status != VendorStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Vendor status is {vendor.status.value}"
        )
    
    return vendor
