"""
Security utilities for authentication and authorization.

Provides password hashing, JWT token generation/validation, and OTP management.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
import secrets
import os

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days default


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
        
    Requirements:
        - Req 1.1: Password hashing for client authentication
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
        
    Requirements:
        - Req 1.1: Password verification for client login
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
        
    Requirements:
        - Req 1.1: JWT token generation for client authentication
        - Req 1.2: Token-based authentication
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT access token.
    
    Args:
        token: JWT token string to decode
        
    Returns:
        Dictionary of token claims if valid, None if invalid
        
    Requirements:
        - Req 1.2: JWT token validation
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_otp(length: int = 6) -> str:
    """
    Generate a random OTP (One-Time Password).
    
    Args:
        length: Length of OTP (default 6 digits)
        
    Returns:
        Random numeric OTP string
        
    Requirements:
        - Req 1.4: OTP generation for vendor authentication
    """
    # Generate cryptographically secure random digits
    otp = ''.join([str(secrets.randbelow(10)) for _ in range(length)])
    return otp


def generate_vendor_id() -> str:
    """
    Generate a unique 6-character alphanumeric vendor ID.
    
    Returns:
        6-character uppercase alphanumeric string (e.g., "A3X9K2")
        
    Requirements:
        - Req 1.1: Vendor ID generation (6-char alphanumeric)
        - Property 12: Campaign code format invariant
    """
    import string
    import random
    
    # Use uppercase letters and digits
    chars = string.ascii_uppercase + string.digits
    # Generate 6 random characters
    vendor_id = ''.join(random.choices(chars, k=6))
    
    return vendor_id


class OTPManager:
    """
    Manages OTP generation, storage, and validation.
    
    In production, this should use Redis for distributed storage.
    For now, using in-memory storage for development.
    """
    
    def __init__(self, expiration_minutes: int = 10):
        """
        Initialize OTP manager.
        
        Args:
            expiration_minutes: How long OTPs are valid (default 10 minutes)
        """
        self.otps: Dict[str, Dict[str, Any]] = {}  # {phone_number: {otp, expires_at}}
        self.expiration_minutes = expiration_minutes
    
    def generate_and_store(self, phone_number: str) -> str:
        """
        Generate and store an OTP for a phone number.
        
        Args:
            phone_number: Phone number to associate with OTP
            
        Returns:
            Generated OTP string
        """
        otp = generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=self.expiration_minutes)
        
        self.otps[phone_number] = {
            "otp": otp,
            "expires_at": expires_at,
            "attempts": 0
        }
        
        return otp
    
    def verify(self, phone_number: str, otp: str, max_attempts: int = 3) -> bool:
        """
        Verify an OTP for a phone number.
        
        Args:
            phone_number: Phone number to verify
            otp: OTP to verify
            max_attempts: Maximum verification attempts allowed
            
        Returns:
            True if OTP is valid, False otherwise
        """
        if phone_number not in self.otps:
            return False
        
        stored = self.otps[phone_number]
        
        # Check if expired
        if datetime.utcnow() > stored["expires_at"]:
            del self.otps[phone_number]
            return False
        
        # Check attempts
        if stored["attempts"] >= max_attempts:
            del self.otps[phone_number]
            return False
        
        # Increment attempts
        stored["attempts"] += 1
        
        # Verify OTP
        if stored["otp"] == otp:
            # Valid OTP - remove it (one-time use)
            del self.otps[phone_number]
            return True
        
        return False
    
    def cleanup_expired(self):
        """Remove expired OTPs from storage."""
        now = datetime.utcnow()
        expired = [
            phone for phone, data in self.otps.items()
            if now > data["expires_at"]
        ]
        for phone in expired:
            del self.otps[phone]


# Global OTP manager instance
otp_manager = OTPManager()



def generate_campaign_code() -> str:
    """
    Generate a unique campaign code with format: PREFIX-YEAR-XXXX
    where XXXX is 4 alphanumeric characters.

    Returns:
        Campaign code string (e.g., "NYC-2026-A3X9")

    Requirements:
        - Req 1.1: Campaign code generation
        - Req 12.1: Campaign code format validation
        - Property 12: Campaign code format invariant
    """
    import string
    import random
    from datetime import datetime

    # Get current year
    year = datetime.utcnow().year

    # Generate 4 random alphanumeric characters
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=4))

    # Use a generic prefix for now (can be customized per client)
    prefix = "CAM"

    # Format: PREFIX-YEAR-XXXX
    campaign_code = f"{prefix}-{year}-{suffix}"

    return campaign_code



class ChallengeManager:
    """
    Manages challenge nonces for device-attested authentication.
    
    Flow:
      1. Device requests challenge → server generates random nonce
      2. Device signs nonce with StrongBox private key
      3. Device sends signature → server verifies with stored public key
    """
    
    def __init__(self, expiration_seconds: int = 300):
        self.challenges: Dict[str, Dict[str, Any]] = {}  # {challenge: {vendor_id, device_id, expires_at}}
        self.expiration_seconds = expiration_seconds
    
    def generate(self, vendor_id: str, device_id: str) -> str:
        """Generate a random challenge nonce."""
        challenge = secrets.token_hex(32)  # 64-char hex string
        expires_at = datetime.utcnow() + timedelta(seconds=self.expiration_seconds)
        
        self.challenges[challenge] = {
            "vendor_id": vendor_id,
            "device_id": device_id,
            "expires_at": expires_at,
        }
        
        # Cleanup old challenges
        self._cleanup()
        
        return challenge
    
    def validate(self, challenge: str, vendor_id: str, device_id: str) -> bool:
        """Validate that a challenge exists and matches the vendor/device."""
        if challenge not in self.challenges:
            return False
        
        stored = self.challenges[challenge]
        
        if datetime.utcnow() > stored["expires_at"]:
            del self.challenges[challenge]
            return False
        
        if stored["vendor_id"] != vendor_id or stored["device_id"] != device_id:
            return False
        
        # One-time use — consume the challenge
        del self.challenges[challenge]
        return True
    
    def _cleanup(self):
        """Remove expired challenges."""
        now = datetime.utcnow()
        expired = [c for c, d in self.challenges.items() if now > d["expires_at"]]
        for c in expired:
            del self.challenges[c]


def verify_ecdsa_signature(public_key_pem: str, challenge: str, signature_b64: str) -> bool:
    """
    Verify an ECDSA signature from Android StrongBox/TEE.
    
    Args:
        public_key_pem: PEM-encoded ECDSA public key from vendor registration
        challenge: The challenge nonce that was signed
        signature_b64: Base64-encoded DER signature from Android
        
    Returns:
        True if signature is valid
    """
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        import base64
        
        # Load public key
        public_key = serialization.load_pem_public_key(public_key_pem.encode())
        
        # Decode signature
        signature_bytes = base64.b64decode(signature_b64)
        
        # Verify — Android StrongBox uses SHA256withECDSA
        public_key.verify(
            signature_bytes,
            challenge.encode(),
            ec.ECDSA(hashes.SHA256())
        )
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"ECDSA verification failed: {e}")
        return False


# Global challenge manager
challenge_manager = ChallengeManager()
