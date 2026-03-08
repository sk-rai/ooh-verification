"""
FastAPI dependencies for quota enforcement.
"""
from typing import Callable
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_client
from app.services.quota_enforcer import QuotaEnforcer, QuotaExceededError, get_quota_enforcer
from app.models.client import Client


async def require_photo_quota(
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Dependency to check photo upload quota.
    
    Raises:
        HTTPException: 402 Payment Required if quota exceeded
    """
    enforcer = get_quota_enforcer(db)
    
    try:
        await enforcer.check_photo_quota(str(current_client.client_id))
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=e.to_dict()
        )


async def require_vendor_quota(
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Dependency to check vendor creation quota.
    
    Raises:
        HTTPException: 402 Payment Required if quota exceeded
    """
    enforcer = get_quota_enforcer(db)
    
    try:
        await enforcer.check_vendor_quota(str(current_client.client_id))
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=e.to_dict()
        )


async def require_campaign_quota(
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Dependency to check campaign creation quota.
    
    Raises:
        HTTPException: 402 Payment Required if quota exceeded
    """
    enforcer = get_quota_enforcer(db)
    
    try:
        await enforcer.check_campaign_quota(str(current_client.client_id))
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=e.to_dict()
        )


def require_storage_quota(file_size_mb: float) -> Callable:
    """
    Dependency factory to check storage quota for specific file size.
    
    Args:
        file_size_mb: File size in MB
        
    Returns:
        Dependency function
    """
    async def _check_storage_quota(
        current_client: Client = Depends(get_current_client),
        db: AsyncSession = Depends(get_db)
    ) -> None:
        enforcer = get_quota_enforcer(db)
        
        try:
            await enforcer.check_storage_quota(str(current_client.client_id), file_size_mb)
        except QuotaExceededError as e:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=e.to_dict()
            )
    
    return _check_storage_quota


async def get_usage_stats_dependency(
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Dependency to get usage statistics for current client.
    
    Returns:
        Usage statistics dictionary
    """
    enforcer = get_quota_enforcer(db)
    return await enforcer.get_usage_stats(str(current_client.client_id))
