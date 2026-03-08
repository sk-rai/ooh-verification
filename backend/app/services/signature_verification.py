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

    SUPPORTED_ALGORITHMS = ["RSA-2048", "ECDSA-P256"]

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
            photo_hash: The hash of the photo to verify
            signature: The signature bytes to verify
            public_key: PEM-encoded public key string
            algorithm: Algorithm used (RSA-2048 or ECDSA-P256)

        Returns:
            bool: True if signature is valid, False otherwise
        """
        if algorithm not in SignatureVerificationService.SUPPORTED_ALGORITHMS:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        try:
            # Load the public key
            public_key_obj = serialization.load_pem_public_key(
                public_key.encode() if isinstance(public_key, str) else public_key,
                backend=default_backend()
            )

            # Verify based on algorithm
            if algorithm == "RSA-2048":
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

            elif algorithm == "ECDSA-P256":
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
    def validate_timestamp(
        timestamp: datetime,
        max_age_minutes: int = 5
    ) -> bool:
        """
        Validate that a timestamp is within acceptable age.

        Args:
            timestamp: The timestamp to validate
            max_age_minutes: Maximum age in minutes (default: 5)

        Returns:
            bool: True if timestamp is valid, False otherwise
        """
        if not isinstance(timestamp, datetime):
            return False

        now = datetime.utcnow()
        age = now - timestamp

        # Check if timestamp is not in the future
        if age.total_seconds() < 0:
            return False

        # Check if timestamp is within max age
        max_age = timedelta(minutes=max_age_minutes)
        return age <= max_age

    @staticmethod
    def validate_location_hash(
        sensor_data: Dict,
        location_hash: str,
        salt: str
    ) -> bool:
        """
        Validate a location hash against sensor data.

        Args:
            sensor_data: Dictionary containing GPS, WiFi, and cell tower data
            location_hash: The hash to validate
            salt: Salt used for hashing

        Returns:
            bool: True if hash is valid, False otherwise
        """
        from app.services.location_hash import LocationHashService

        try:
            # Extract sensor data
            gps_coords = sensor_data.get("gps_coords")
            wifi_bssids = sensor_data.get("wifi_bssids", [])
            cell_tower_ids = sensor_data.get("cell_tower_ids", [])

            if gps_coords is None:
                return False

            # Generate expected hash
            expected_hash = LocationHashService.generate_location_hash(
                gps_coords=gps_coords,
                wifi_bssids=wifi_bssids,
                cell_tower_ids=cell_tower_ids,
                salt=salt
            )

            # Compare hashes
            return expected_hash == location_hash

        except Exception:
            return False
