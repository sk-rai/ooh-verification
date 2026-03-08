"""
Pydantic schemas for TrustCapture API.
"""
from app.schemas.auth import (
    ClientRegister,
    ClientLogin,
    VendorLogin,
    VendorVerifyOTP,
    VendorRegisterDevice,
    Token,
    TokenData,
    ClientResponse,
    VendorResponse,
    OTPResponse
)
from app.schemas.client import (
    ClientProfileUpdate,
    SubscriptionResponse
)
from app.schemas.vendor import (
    VendorCreate,
    VendorUpdate,
    VendorResponse as VendorDetailResponse,
    VendorListResponse
)

__all__ = [
    "ClientRegister",
    "ClientLogin",
    "VendorLogin",
    "VendorVerifyOTP",
    "VendorRegisterDevice",
    "Token",
    "TokenData",
    "ClientResponse",
    "VendorResponse",
    "OTPResponse",
    "ClientProfileUpdate",
    "SubscriptionResponse",
    "VendorCreate",
    "VendorUpdate",
    "VendorDetailResponse",
    "VendorListResponse",
]
