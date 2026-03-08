"""
Photo Signature Verification Service

Implements cryptographic verification of photo signatures using RSA/ECDSA.

Requirements:
- Req 8.1-8.7: Cryptographic photo signing
- Req 27.1-27.6: Photo signature verification
- Property 3: Photo signature verification inverse
- Property 13: Photo signature tamper detection
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature


class SignatureVerificationService:
    """
    Service for verifying cryptographic signatures on photos.
    
    Supports both RSA-2048 and ECDSA P-256 signature algorithms.
    """
    
    # Timestamp validation window (5 minutes)
    TIMESTAMP_WINDOW_MINUTES = 5
    
    # Supported algorithms
    SUPPORTED_ALGORITHMS = {"SHA256withRSA", "SHA256withECDSA"}
    
    def __init__(self):
        """Initialize the signature verification service."""
        self.backend = default_backend()
    
    def verify_photo_signature(
        self,
        photo_hash: str,
        signature_data: str,
        public_key_pem: str,
        algorithm: str,
        timestamp: datetime,
        location_hash: str,
        sensor_data_location_hash: str,
        server_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Verify a photo signature with comprehensive validation.
        
        Args:
            photo_hash: SHA-256 hash of the photo (hex string)
            signature_data: Base64-encoded signature
            public_key_pem: PEM-encoded public key
            algorithm: Signature algorithm ('SHA256withRSA' or 'SHA256withECDSA')
            timestamp: Signature timestamp
            location_hash: Location hash from signature
            sensor_data_location_hash: Location hash from sensor data
            server_time: Server time for timestamp validation (defaults to now)
        
        Returns:
            Dictionary with verification results:
            {
                'valid': bool,
                'signature_valid': bool,
                'timestamp_valid': bool,
                'location_hash_valid': bool,
                'errors': List[str]
            }
        
        Requirements:
            - Req 8.1: Signature verification using RSA/ECDSA
            - Req 8.2: Validate signature matches photo hash
            - Req 8.3: Validate timestamp within 5-minute window
            - Req 8.4: Validate location hash matches sensor data
            - Req 27.1-27.5: Server-side signature verification
        """
        errors = []
        signature_valid = False
        timestamp_valid = False
        location_hash_valid = False
        
        # Validate algorithm
        if algorithm not in self.SUPPORTED_ALGORITHMS:
            errors.append(f"Unsupported algorithm: {algorithm}")
            return {
                'valid': False,
                'signature_valid': False,
                'timestamp_valid': False,
                'location_hash_valid': False,
                'errors': errors
            }
        
        # Validate timestamp (Req 27.4)
        timestamp_valid = self._validate_timestamp(timestamp, server_time)
        if not timestamp_valid:
            errors.append("Timestamp outside 5-minute window")
        
        # Validate location hash (Req 27.5)
        location_hash_valid = self._validate_location_hash(
            location_hash,
            sensor_data_location_hash
        )
        if not location_hash_valid:
            errors.append("Location hash mismatch")
        
        # Verify cryptographic signature (Req 27.1-27.3)
        try:
            signature_valid = self._verify_signature(
                photo_hash=photo_hash,
                signature_data=signature_data,
                public_key_pem=public_key_pem,
                algorithm=algorithm,
                timestamp=timestamp,
                location_hash=location_hash
            )
            if not signature_valid:
                errors.append("Invalid cryptographic signature")
        except Exception as e:
            errors.append(f"Signature verification error: {str(e)}")
            signature_valid = False
        
        # Overall validity requires all checks to pass
        valid = signature_valid and timestamp_valid and location_hash_valid
        
        return {
            'valid': valid,
            'signature_valid': signature_valid,
            'timestamp_valid': timestamp_valid,
            'location_hash_valid': location_hash_valid,
            'errors': errors
        }
    
    def _validate_timestamp(
        self,
        signature_timestamp: datetime,
        server_time: Optional[datetime] = None
    ) -> bool:
        """
        Validate that signature timestamp is within acceptable window.
        
        Args:
            signature_timestamp: Timestamp from signature
            server_time: Server time for comparison (defaults to now)
        
        Returns:
            True if timestamp is within 5-minute window
        
        Requirements:
            - Req 27.4: Timestamp within 5 minutes to prevent replay attacks
        """
        if server_time is None:
            server_time = datetime.utcnow()
        
        time_diff = abs((server_time - signature_timestamp).total_seconds())
        max_diff_seconds = self.TIMESTAMP_WINDOW_MINUTES * 60
        
        return time_diff <= max_diff_seconds
    
    def _validate_location_hash(
        self,
        signature_location_hash: str,
        sensor_data_location_hash: str
    ) -> bool:
        """
        Validate that location hash in signature matches sensor data.
        
        Args:
            signature_location_hash: Location hash from signature
            sensor_data_location_hash: Location hash from sensor data
        
        Returns:
            True if hashes match
        
        Requirements:
            - Req 27.5: Location hash validation
        """
        return signature_location_hash == sensor_data_location_hash
    
    def _verify_signature(
        self,
        photo_hash: str,
        signature_data: str,
        public_key_pem: str,
        algorithm: str,
        timestamp: datetime,
        location_hash: str
    ) -> bool:
        """
        Verify the cryptographic signature.
        
        Args:
            photo_hash: SHA-256 hash of photo
            signature_data: Base64-encoded signature
            public_key_pem: PEM-encoded public key
            algorithm: Signature algorithm
            timestamp: Signature timestamp
            location_hash: Location hash
        
        Returns:
            True if signature is valid
        
        Requirements:
            - Req 8.1: RSA/ECDSA signature verification
            - Req 8.2: Validate signature matches photo hash
            - Req 27.2: Verify signature with public key
        """
        # Decode signature
        try:
            signature_bytes = base64.b64decode(signature_data)
        except Exception:
            return False
        
        # Load public key
        try:
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode('utf-8'),
                backend=self.backend
            )
        except Exception:
            return False
        
        # Construct signed data (photo_hash + timestamp + location_hash)
        signed_data = self._construct_signed_data(
            photo_hash,
            timestamp,
            location_hash
        )
        
        # Verify signature based on algorithm
        try:
            if algorithm == "SHA256withRSA":
                return self._verify_rsa_signature(
                    public_key,
                    signature_bytes,
                    signed_data
                )
            elif algorithm == "SHA256withECDSA":
                return self._verify_ecdsa_signature(
                    public_key,
                    signature_bytes,
                    signed_data
                )
            else:
                return False
        except InvalidSignature:
            return False
        except Exception:
            return False
    
    def _construct_signed_data(
        self,
        photo_hash: str,
        timestamp: datetime,
        location_hash: str
    ) -> bytes:
        """
        Construct the data that was signed.
        
        Format: photo_hash + timestamp_iso + location_hash
        
        Args:
            photo_hash: SHA-256 hash of photo
            timestamp: Signature timestamp
            location_hash: Location hash
        
        Returns:
            Bytes to verify signature against
        """
        timestamp_iso = timestamp.isoformat()
        data_string = f"{photo_hash}{timestamp_iso}{location_hash}"
        return data_string.encode('utf-8')
    
    def _verify_rsa_signature(
        self,
        public_key: rsa.RSAPublicKey,
        signature: bytes,
        data: bytes
    ) -> bool:
        """
        Verify RSA signature.
        
        Args:
            public_key: RSA public key
            signature: Signature bytes
            data: Data that was signed
        
        Returns:
            True if signature is valid
        
        Requirements:
            - Req 8.4: RSA-2048 signature verification
        """
        try:
            public_key.verify(
                signature,
                data,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            return True
        except InvalidSignature:
            return False
    
    def _verify_ecdsa_signature(
        self,
        public_key: ec.EllipticCurvePublicKey,
        signature: bytes,
        data: bytes
    ) -> bool:
        """
        Verify ECDSA signature.
        
        Args:
            public_key: ECDSA public key
            signature: Signature bytes
            data: Data that was signed
        
        Returns:
            True if signature is valid
        
        Requirements:
            - Req 8.4: ECDSA P-256 signature verification
        """
        try:
            public_key.verify(
                signature,
                data,
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except InvalidSignature:
            return False
    
    def compute_photo_hash(self, photo_bytes: bytes) -> str:
        """
        Compute SHA-256 hash of photo.
        
        Args:
            photo_bytes: Photo file bytes
        
        Returns:
            Hex-encoded SHA-256 hash
        
        Requirements:
            - Req 8.4: SHA-256 hashing
        """
        return hashlib.sha256(photo_bytes).hexdigest()
    
    def store_public_key(self, vendor_id: str, public_key_pem: str) -> bool:
        """
        Store vendor's public key for signature verification.
        
        This method would typically update the vendor record in the database.
        
        Args:
            vendor_id: Vendor identifier
            public_key_pem: PEM-encoded public key
        
        Returns:
            True if stored successfully
        
        Requirements:
            - Req 8.7: Store public keys from vendor devices
            - Req 12.6: Public key storage
        """
        # This is a placeholder - actual implementation would update database
        # through a repository or ORM
        try:
            # Validate the public key can be loaded
            serialization.load_pem_public_key(
                public_key_pem.encode('utf-8'),
                backend=self.backend
            )
            return True
        except Exception:
            return False
