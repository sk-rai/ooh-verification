"""
Client Management API endpoints.

Provides client profile management, subscription management, and account operations.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_active_client
from app.models import Client, Subscription
from app.schemas.client import (
    ClientProfileUpdate, ClientResponse, SubscriptionResponse
)

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("/me", response_model=ClientResponse)
async def get_current_client_profile(
    client: Client = Depends(get_current_active_client)
):
    """
    Get current authenticated client profile.
    
    Requirements:
        - Req 1.1: Client profile access
        - Req 1.2: Subscription information
    """
    return client


@router.patch("/me", response_model=ClientResponse)
async def update_current_client_profile(
    data: ClientProfileUpdate,
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current client profile information.
    
    Requirements:
        - Req 1.1: Client profile management
    """
    # Update fields if provided
    if data.company_name is not None:
        client.company_name = data.company_name
    if data.phone_number is not None:
        client.phone_number = data.phone_number
    
    client.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(client)
    
    return client


@router.get("/me/subscription", response_model=SubscriptionResponse)
async def get_current_subscription(
    client: Client = Depends(get_current_active_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current client subscription details.
    
    Requirements:
        - Req 1.2: Subscription tier information
        - Usage tracking and quota management
    """
    # Get subscription
    result = await db.execute(
        select(Subscription).where(Subscription.client_id == client.client_id)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    return subscription
