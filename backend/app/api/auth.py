import logging
"""
Authentication API endpoints.

Provides client and vendor authentication, registration, and token management.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import uuid

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_access_token,
    otp_manager, challenge_manager, verify_ecdsa_signature,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.core.deps import get_current_active_client, get_current_active_vendor
from app.models import Client, Vendor, Subscription
from app.models.client import SubscriptionTier, SubscriptionStatus
from app.models.vendor import VendorStatus
from app.schemas.auth import (
    ClientRegister, ClientLogin, VendorLogin, VendorVerifyOTP,
    VendorRegisterDevice, Token, ClientResponse, VendorResponse, OTPResponse,
    ChallengeRequest, ChallengeResponse, DeviceLoginRequest
)
from app.middleware.tenant_context import get_current_tenant
from app.core.sms import sms_service
from app.services.email_service import get_email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def register_client(
    data: ClientRegister,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new client account.
    
    Requirements:
        - Req 1.1: Client registration with email/password
        - Req 1.2: Subscription tier management
    """
    tenant_id = get_current_tenant(request)
    
    # Check if email already exists
    result = await db.execute(
        select(Client).where(Client.email == data.email, Client.tenant_id == tenant_id)
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
        tenant_id=tenant_id,
        email=data.email,
        password_hash=hash_password(data.password),
        company_name=data.company_name,
        phone_number=data.phone_number,
        contact_person=getattr(data, 'contact_person', None),
        contact_phone=getattr(data, 'contact_phone', None),
        designation=getattr(data, 'designation', None),
        title=getattr(data, 'title', None),
        address=getattr(data, 'address', None),
        city=getattr(data, 'city', None),
        state=getattr(data, 'state', None),
        country=getattr(data, 'country', None),
        website=getattr(data, 'website', None),
        industry=getattr(data, 'industry', None),
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
        tenant_id=tenant_id,
        tier=SubscriptionTier.FREE,
        status=SubscriptionStatus.ACTIVE,
        photos_quota=50,  # Free tier: 50 photos/month
        photos_used=0,
        vendors_quota=5,  # Free tier: 5 vendors
        vendors_used=0,
        campaigns_quota=10,  # Free tier: 10 campaigns
        campaigns_used=0,
        storage_quota_mb=100,  # Free tier: 100 MB storage
        storage_used_mb=0,
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(subscription)
    await db.commit()
    await db.refresh(client)
    
    # Send welcome email (fire-and-forget)
    try:
        email_svc = get_email_service(db)
        await email_svc.send_templated_email(
            tenant_id=str(tenant_id),
            template_name="welcome_email",
            to_email=data.email,
            variables={
                "user_name": data.company_name or data.email,
                "user_email": data.email,
                "login_url": "https://trustcapture-web.onrender.com/login",
            }
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Welcome email failed (non-critical): {str(e)}")

    return client


@router.post("/login", response_model=Token)
async def login_client(
    data: ClientLogin,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Login as a client and receive JWT token.
    
    Requirements:
        - Req 1.1: Client login with JWT
        - Req 1.2: Token-based authentication
    """
    tenant_id = get_current_tenant(request)
    
    # Get client by email
    result = await db.execute(
        select(Client).where(Client.email == data.email, Client.tenant_id == tenant_id)
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
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Request OTP for vendor login (Step 1).
    
    Requirements:
        - Req 1.4: Vendor login with OTP
        - Req 1.3: SMS delivery
    """
    tenant_id = get_current_tenant(request)
    
    # Verify vendor exists and phone number matches
    result = await db.execute(
        select(Vendor).where(
            Vendor.vendor_id == data.vendor_id,
            Vendor.tenant_id == tenant_id,
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
    # Play Store review test account — bypass SMS
        if data.phone_number == "+911234567890":
            # Store hardcoded OTP for test account
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text
            from datetime import datetime, timedelta
            async with AsyncSessionLocal() as test_db:
                await test_db.execute(text(
                    "INSERT INTO otp_codes (phone_number, otp, expires_at, attempts) "
                    "VALUES (:phone, '123456', :expires, 0) "
                    "ON CONFLICT (phone_number) DO UPDATE SET otp = '123456', expires_at = :expires, attempts = 0"
                ), {"phone": "+911234567890", "expires": datetime.utcnow() + timedelta(hours=24)})
                await test_db.commit()
            otp = "123456"
            # Skip SMS sending for test account
            return {"message": "OTP sent successfully", "expires_in": 86400}

        otp = await otp_manager.async_generate_and_store(data.phone_number)
    
    # Send OTP via SMS (Twilio)
    sms_sent = await sms_service.send_otp_sms(data.phone_number, otp)

    if not sms_sent:
        print(f"⚠️ SMS delivery failed for {data.phone_number}, OTP: {otp}")
    
    return {
        "message": "OTP sent to your phone number",
        "expires_in": 600  # 10 minutes
    }


@router.post("/vendor/verify-otp", response_model=Token)
async def vendor_verify_otp(
    data: VendorVerifyOTP,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify OTP and login as vendor (Step 2).
    
    Requirements:
        - Req 1.4: Vendor OTP verification
        - Req 12.6: Device registration
    """
    tenant_id = get_current_tenant(request)
    
    # Verify OTP
    if not await otp_manager.async_verify(data.phone_number, data.otp):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP"
        )
    
    # Get vendor
    result = await db.execute(
        select(Vendor).where(
            Vendor.vendor_id == data.vendor_id,
            Vendor.tenant_id == tenant_id,
            Vendor.phone_number == data.phone_number
        )
    )
    vendor = result.scalar_one_or_none()
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )
    
    # Update device ID if provided (always update to latest device)
    if data.device_id:
        vendor.device_id = data.device_id
    
    # Mark device as verified (first OTP login completes registration)
    if not vendor.device_verified:
        vendor.device_verified = True
    vendor.last_login_at = datetime.utcnow()
    await db.commit()
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": vendor.vendor_id,
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
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Register vendor device and public key.
    
    Requirements:
        - Req 12.6: Public key storage for signature verification
    """
    tenant_id = get_current_tenant(request)
    
    # Get vendor by device ID
    result = await db.execute(
        select(Vendor).where(Vendor.device_id == data.device_id, Vendor.tenant_id == tenant_id)
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




@router.post("/vendor/challenge", response_model=ChallengeResponse)
async def vendor_request_challenge(
    data: ChallengeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Request a challenge nonce for device-attested login (Step 1 of device auth).
    
    The device signs this challenge with its StrongBox private key and sends
    the signature to /vendor/device-login.
    
    Requirements:
        - Device must be registered (device_id + public_key set)
        - Vendor must have completed first OTP login (device_verified=True)
    """
    tenant_id = get_current_tenant(request)
    
    # Verify vendor exists with this device
    result = await db.execute(
        select(Vendor).where(
            Vendor.vendor_id == data.vendor_id,
            Vendor.tenant_id == tenant_id,
            Vendor.device_id == data.device_id
        )
    )
    vendor = result.scalar_one_or_none()
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found or device not registered"
        )
    
    if vendor.status != VendorStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Vendor status is {vendor.status.value}"
        )
    
    if not vendor.device_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device not verified. Complete OTP login first."
        )
    
    if not vendor.public_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No public key registered. Complete device registration first."
        )
    
    # Generate challenge
    challenge = challenge_manager.generate(data.vendor_id, data.device_id)
    
    return {
        "challenge": challenge,
        "expires_in": 300  # 5 minutes
    }


@router.post("/vendor/device-login", response_model=Token)
async def vendor_device_login(
    data: DeviceLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Device-attested login using StrongBox signature (Step 2 of device auth).
    
    Flow:
      1. Device got challenge from /vendor/challenge
      2. Device signed challenge with StrongBox ECDSA private key
      3. This endpoint verifies signature against stored public key
      4. If valid, issues JWT token — no SMS needed
    
    Requirements:
        - Req 1.4: Vendor authentication (device-attested variant)
        - Req 12.6: Public key verification
    """
    tenant_id = get_current_tenant(request)
    
    # Validate challenge
    if not challenge_manager.validate(data.challenge, data.vendor_id, data.device_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired challenge"
        )
    
    # Get vendor
    result = await db.execute(
        select(Vendor).where(
            Vendor.vendor_id == data.vendor_id,
            Vendor.tenant_id == tenant_id,
            Vendor.device_id == data.device_id
        )
    )
    vendor = result.scalar_one_or_none()
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )
    
    if not vendor.public_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No public key registered for this device"
        )
    
    # Verify ECDSA signature
    if not verify_ecdsa_signature(vendor.public_key, data.challenge, data.signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature verification failed"
        )
    
    # Update last login
    vendor.last_login_at = datetime.utcnow()
    await db.commit()
    
    # Issue JWT token
    access_token = create_access_token(
        data={
            "sub": vendor.vendor_id,
            "type": "vendor",
            "vendor_id": vendor.vendor_id,
            "auth_method": "device_attestation"
        }
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

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
