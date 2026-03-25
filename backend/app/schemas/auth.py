"""
Pydantic schemas for authentication endpoints.
"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID


class ClientRegister(BaseModel):
    """Schema for client registration."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    company_name: str = Field(..., min_length=2, max_length=255)
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$', description="Valid phone number with country code")
    contact_person: Optional[str] = Field(None, max_length=255, description="Contact person name")
    contact_phone: Optional[str] = Field(None, max_length=20, description="Contact person phone/cell")
    designation: Optional[str] = Field(None, max_length=100, description="Designation in company")
    title: Optional[str] = Field(None, max_length=10, description="Title/prefix e.g. Mr, Ms, Mrs, Dr")
    address: Optional[str] = Field(None, max_length=500, description="Company address")
    city: Optional[str] = Field(None, max_length=100, description="City")
    state: Optional[str] = Field(None, max_length=100, description="State/Province")
    country: str = Field(..., max_length=100, description="Country")
    website: Optional[str] = Field(None, max_length=500, description="Company website URL")
    industry: Optional[str] = Field(None, max_length=100, description="Industry sector")

    @field_validator('password')
    @classmethod
    def password_strength(cls, v):
        """Validate password strength."""
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        return v

    class Config:
        schema_extra = {
            "example": {
                "email": "client@example.com",
                "password": "SecurePass123",
                "company_name": "Acme Corporation",
                "phone_number": "+1234567890"
            }
        }


class ClientLogin(BaseModel):
    """Schema for client login."""
    email: EmailStr
    password: str

    class Config:
        schema_extra = {
            "example": {
                "email": "client@example.com",
                "password": "SecurePass123"
            }
        }


class VendorLogin(BaseModel):
    """Schema for vendor login - step 1: request OTP."""
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    vendor_id: str = Field(..., min_length=6, max_length=6, pattern=r'^[A-Z0-9]{6}$')

    class Config:
        schema_extra = {
            "example": {
                "phone_number": "+1234567890",
                "vendor_id": "ABC123"
            }
        }


class VendorVerifyOTP(BaseModel):
    """Schema for vendor OTP verification - step 2: verify OTP."""
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    vendor_id: str = Field(..., min_length=6, max_length=6, pattern=r'^[A-Z0-9]{6}$')
    otp: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$')
    device_id: Optional[str] = Field(None, description="Android device ID for registration")

    class Config:
        schema_extra = {
            "example": {
                "phone_number": "+1234567890",
                "vendor_id": "ABC123",
                "otp": "123456",
                "device_id": "android-device-uuid"
            }
        }


class VendorRegisterDevice(BaseModel):
    """Schema for vendor device registration."""
    device_id: str = Field(..., description="Android device unique identifier")
    public_key: str = Field(..., description="RSA/ECDSA public key from Android Keystore")

    class Config:
        schema_extra = {
            "example": {
                "device_id": "android-device-uuid",
                "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...\n-----END PUBLIC KEY-----"
            }
        }


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token expiration time in seconds")

    class Config:
        schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 604800
            }
        }


class TokenData(BaseModel):
    """Schema for decoded token data."""
    user_id: str
    user_type: str  # "client" or "vendor"
    email: Optional[str] = None
    vendor_id: Optional[str] = None


class ClientResponse(BaseModel):
    """Schema for client information response."""
    client_id: str
    email: str
    company_name: str
    phone_number: str
    subscription_tier: str
    subscription_status: str
    created_at: datetime

    @field_validator('client_id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "client_id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "client@example.com",
                "company_name": "Acme Corporation",
                "phone_number": "+1234567890",
                "subscription_tier": "pro",
                "subscription_status": "active",
                "created_at": "2026-03-04T12:00:00Z"
            }
        }


class VendorResponse(BaseModel):
    """Schema for vendor information response."""
    vendor_id: str
    name: str
    phone_number: str
    email: Optional[str]
    status: str
    device_id: Optional[str]
    created_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "vendor_id": "ABC123",
                "name": "John Doe",
                "phone_number": "+1234567890",
                "email": "john@example.com",
                "status": "active",
                "device_id": "android-device-uuid",
                "created_at": "2026-03-04T12:00:00Z",
                "last_login_at": "2026-03-04T14:30:00Z"
            }
        }


class OTPResponse(BaseModel):
    """Schema for OTP request response."""
    message: str
    expires_in: int = Field(..., description="OTP expiration time in seconds")

    class Config:
        schema_extra = {
            "example": {
                "message": "OTP sent to your phone number",
                "expires_in": 600
            }
        }


class ChallengeRequest(BaseModel):
    """Request a challenge nonce for device-attested login."""
    vendor_id: str = Field(..., min_length=6, max_length=6, pattern=r'^[A-Z0-9]{6}$')
    device_id: str = Field(..., description="Registered device ID")

    class Config:
        schema_extra = {
            "example": {
                "vendor_id": "ABC123",
                "device_id": "android-device-uuid"
            }
        }


class ChallengeResponse(BaseModel):
    """Challenge nonce for device to sign."""
    challenge: str = Field(..., description="Random nonce to sign with device private key")
    expires_in: int = Field(..., description="Challenge expiration in seconds")

    class Config:
        schema_extra = {
            "example": {
                "challenge": "a1b2c3d4e5f6...",
                "expires_in": 300
            }
        }


class DeviceLoginRequest(BaseModel):
    """Device-attested login using StrongBox signature."""
    vendor_id: str = Field(..., min_length=6, max_length=6, pattern=r'^[A-Z0-9]{6}$')
    device_id: str = Field(..., description="Registered device ID")
    challenge: str = Field(..., description="The challenge nonce that was signed")
    signature: str = Field(..., description="Base64-encoded ECDSA signature of the challenge")

    class Config:
        schema_extra = {
            "example": {
                "vendor_id": "ABC123",
                "device_id": "android-device-uuid",
                "challenge": "a1b2c3d4e5f6...",
                "signature": "MEUCIQD..."
            }
        }
