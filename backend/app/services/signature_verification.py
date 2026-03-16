"""Photo signature verification service for TrustCapture."""

from datetime import datetime, timedelta
from typing import Dict
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature
import hashlib


class SignatureVerificationService:
    """Service for verifying cryptographic signatures on photos."""

    SUPPORTED_ALGORITHMS = ["RSA-2048", "ECDSA-P256", "ECDSA-SHA256"]

    @staticmethod
    def verify_signature(
        photo_hash: bytes,
        signature: bytes,
        public_key: str,
        algorithm: str
    ) -> bool:
        """
        Verify a cryptographic signature on a photo hash.

        Args:
            photo_hash: The data bytes that were signed (NOT raw photo bytes)
            signature: The signature bytes to verify
            public_key: PEM-encoded public key string
            algorithm: Algorithm used (RSA-2048, ECDSA-P256, or ECDSA-SHA256)

        Returns:
            bool: True if signature is valid, False otherwise
        """
        # Normalize algorithm name
        normalized_algo = algorithm
        if algorithm == "ECDSA-SHA256":
            normalized_algo = "ECDSA-P256"

        if normalized_algo not in ["RSA-2048", "ECDSA-P256"]:
            raise ValueError(f"Unsupported algorithm: {algorithm}")


        try:
            # Load the public key
            public_key_obj = serialization.load_pem_public_key(
                public_key.encode() if isinstance(public_key, str) else public_key,
                backend=default_backend()
            )

            if normalized_algo == "RSA-2048":
                if not isinstance(public_key_obj, rsa.RSAPublicKey):
                    return False
                public_key_obj.verify(
                    signature,
                    photo_hash,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
                return True

            elif normalized_algo == "ECDSA-P256":
                if not isinstance(public_key_obj, ec.EllipticCurvePublicKey):
                    return False
                public_key_obj.verify(
                    signature,
                    photo_hash,
                    ec.ECDSA(hashes.SHA256())
                )
                return True

        except InvalidSignature:
            return False
        except Exception:
            return False

        return False


    @staticmethod
    def build_signed_payload(photo_hash_hex: str, location_hash: str, timestamp: str) -> bytes:
        """
        Reconstruct the composite payload that the Android app signs.
        
        Android signs: "photoHash|locationHash|timestamp" as UTF-8 bytes.
        
        Args:
            photo_hash_hex: SHA-256 hex string of the photo bytes
            location_hash: Location hash from the signature payload
            timestamp: ISO 8601 timestamp string from the signature payload
            
        Returns:
            bytes: The composite payload bytes to verify against
        """
        payload = f"{photo_hash_hex}|{location_hash}|{timestamp}"
        return payload.encode('utf-8')

    @staticmethod
    def validate_timestamp(timestamp: datetime, max_age_minutes: int = 5) -> bool:
        """Validate that a timestamp is within acceptable age."""
        if not isinstance(timestamp, datetime):
            return False
        now = datetime.utcnow()
        age = now - timestamp
        if age.total_seconds() < 0:
            return False
        max_age = timedelta(minutes=max_age_minutes)
        return age <= max_age

    @staticmethod
    def validate_location_hash(sensor_data: Dict, location_hash: str, salt: str) -> bool:
        """Validate a location hash against sensor data."""
        from app.services.location_hash import LocationHashService
        try:
            gps_coords = sensor_data.get("gps_coords")
            wifi_bssids = sensor_data.get("wifi_bssids", [])
            cell_tower_ids = sensor_data.get("cell_tower_ids", [])
            if gps_coords is None:
                return False
            expected_hash = LocationHashService.generate_location_hash(
                gps_coords=gps_coords,
                wifi_bssids=wifi_bssids,
                cell_tower_ids=cell_tower_ids,
                salt=salt
            )
            return expected_hash == location_hash
        except Exception:
            return False
