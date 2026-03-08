"""
Authentication API endpoints.

Provides client and vendor authentication, registration, and token management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import uuid

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_access_token,
    otp_manager, ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.core.deps import get_current_active_client, get_current_active_vendor
from app.models import Client, Vendor, Subscription
from app.models.client import SubscriptionTier, SubscriptionStatus
from app.models.vendor import VendorStatus
from app.schemas.auth import (
    ClientRegister, ClientLogin, VendorLogin, VendorVerifyOTP,
    VendorRegisterDevice, Token, ClientResponse, VendorResponse, OTPResponse
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def register_client(
    data: ClientRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new client account.
    
    Requirements:
        - Req 1.1: Client registration with email/password
        - Req 1.2: Subscription tier management
    """
    # Check if email already exists
    result = await db.execute(
        select(Client).where(Client.email == data.email)
    )
    existing_client = result.scalar_one_or_none()
    
    if existing_client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new client
    client = Client(
        client_id=uuid.uuid4(),
        email=data.email,
        password_hash=hash_password(data.password),
        company_name=data.company_name,
        phone_number=data.phone_number,
        subscription_tier=SubscriptionTier.FREE,  # Default to free tier
        subscription_status=SubscriptionStatus.ACTIVE,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(client)
    await db.flush()
    
    # Create default subscription
    subscription = Subscription(
        subscription_id=uuid.uuid4(),
        client_id=client.client_id,
        tier=SubscriptionTier.FREE,
        status=SubscriptionStatus.ACTIVE,
        photos_quota=50,  # Free tier: 50 photos/month
        photos_used=0,
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(subscription)
    await db.commit()
    await db.refresh(client)
    
    # TODO: Send welcome email via SendGrid
    
    return client


@router.post("/login", response_model=Token)
async def login_client(
    data: ClientLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Login as a client and receive JWT token.
    
    Requirements:
        - Req 1.1: Client login with JWT
        - Req 1.2: Token-based authentication
    """
    # Get client by email
    result = await db.execute(
        select(Client).where(Client.email == data.email)
    )
    client = result.scalar_one_or_none()
    
    # Verify credentials
    if not client or not verify_password(data.password, client.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if subscription is active
    if client.subscription_status != SubscriptionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account subscription is {client.subscription_status.value}"
        )
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": str(client.client_id),
            "type": "client",
            "email": client.email
        }
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    }


@router.post("/vendor/request-otp", response_model=OTPResponse)
async def vendor_request_otp(
    data: VendorLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Request OTP for vendor login (Step 1).
    
    Requirements:
        - Req 1.4: Vendor login with OTP
        - Req 1.3: SMS delivery
    """
    # Verify vendor exists and phone number matches
    result = await db.execute(
        select(Vendor).where(
            Vendor.vendor_id == data.vendor_id,
            Vendor.phone_number == data.phone_number
        )
    )
    vendor = result.scalar_one_or_none()
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found or phone number does not match"
        )
    
    # Check if vendor is active
    if vendor.status != VendorStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Vendor status is {vendor.status.value}"
        )
    
    # Generate and store OTP
    otp = otp_manager.generate_and_store(data.phone_number)
    
    # TODO: Send OTP via Twilio SMS
    # For development, we'll log it
    print(f"[DEV] OTP for {data.phone_number}: {otp}")
    
    return {
        "message": "OTP sent to your phone number",
        "expires_in": 600  # 10 minutes
    }


@router.post("/vendor/verify-otp", response_model=Token)
async def vendor_verify_otp(
    data: VendorVerifyOTP,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify OTP and login as vendor (Step 2).
    
    Requirements:
        - Req 1.4: Vendor OTP verification
        - Req 12.6: Device registration
    """
    # Verify OTP
    if not otp_manager.verify(data.phone_number, data.otp):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP"
        )
    
    # Get vendor
    result = await db.execute(
        select(Vendor).where(
            Vendor.vendor_id == data.vendor_id,
            Vendor.phone_number == data.phone_number
        )
    )
    vendor = result.scalar_one_or_none()
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )
    
    # Update device ID if provided (first-time login)
    if data.device_id and not vendor.device_id:
        vendor.device_id = data.device_id
    
    # Update last login
    vendor.last_login_at = datetime.utcnow()
    await db.commit()
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": str(vendor.created_by_client_id),  # Client ID for authorization
            "type": "vendor",
            "vendor_id": vendor.vendor_id
        }
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.post("/vendor/register-device", response_model=VendorResponse)
async def register_vendor_device(
    data: VendorRegisterDevice,
    db: AsyncSession = Depends(get_db)
):
    """
    Register vendor device and public key.
    
    Requirements:
        - Req 12.6: Public key storage for signature verification
    """
    # Get vendor by device ID
    result = await db.execute(
        select(Vendor).where(Vendor.device_id == data.device_id)
    )
    vendor = result.scalar_one_or_none()
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found for this device"
        )
    
    # Store public key
    vendor.public_key = data.public_key
    await db.commit()
    await db.refresh(vendor)
    
    return vendor


@router.get("/me/client", response_model=ClientResponse)
async def get_current_client_info(
    client: Client = Depends(get_current_active_client)
):
    """
    Get current authenticated client information.

    Requires: JWT token in Authorization header
    Requirements:
        - Req 1.1: Client profile access
        - Req 1.2: Token-based authentication
    """
    return client



@router.get("/me/vendor", response_model=VendorResponse)
async def get_current_vendor_info(
    db: AsyncSession = Depends(get_db)
):
    """
    Get current authenticated vendor information.
    
    Requires: JWT token in Authorization header
    """
    # TODO: Add authentication dependency
    # For now, return placeholder
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Endpoint requires authentication middleware"
    )
