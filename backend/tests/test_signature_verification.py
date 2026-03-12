"""Unit tests for SignatureVerificationService."""

import pytest
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding
from cryptography.hazmat.backends import default_backend

from app.services.signature_verification import SignatureVerificationService


class TestSignatureVerificationService:
    """Test suite for SignatureVerificationService."""

    @pytest.fixture
    def rsa_key_pair(self):
        """Generate RSA-2048 key pair for testing."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        # Serialize public key to PEM format
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        return private_key, public_pem

    @pytest.fixture
    def ecdsa_key_pair(self):
        """Generate ECDSA P-256 key pair for testing."""
        private_key = ec.generate_private_key(
            ec.SECP256R1(),
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        # Serialize public key to PEM format
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        return private_key, public_pem

    @pytest.fixture
    def sample_photo_hash(self):
        """Generate a sample photo hash."""
        return b"sample_photo_hash_data_for_testing"

    def test_verify_signature_rsa_valid(self, rsa_key_pair, sample_photo_hash):
        """Test RSA signature verification with valid signature."""
        private_key, public_pem = rsa_key_pair
        
        # Sign the photo hash
        signature = private_key.sign(
            sample_photo_hash,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Verify the signature
        result = SignatureVerificationService.verify_signature(
            photo_hash=sample_photo_hash,
            signature=signature,
            public_key=public_pem,
            algorithm="RSA-2048"
        )
        
        assert result is True

    def test_verify_signature_rsa_invalid(self, rsa_key_pair, sample_photo_hash):
        """Test RSA signature verification with invalid signature."""
        _, public_pem = rsa_key_pair
        
        # Use a fake signature
        fake_signature = b"invalid_signature_data"
        
        # Verify should fail
        result = SignatureVerificationService.verify_signature(
            photo_hash=sample_photo_hash,
            signature=fake_signature,
            public_key=public_pem,
            algorithm="RSA-2048"
        )
        
        assert result is False

    def test_verify_signature_ecdsa_valid(self, ecdsa_key_pair, sample_photo_hash):
        """Test ECDSA signature verification with valid signature."""
        private_key, public_pem = ecdsa_key_pair
        
        # Sign the photo hash
        signature = private_key.sign(
            sample_photo_hash,
            ec.ECDSA(hashes.SHA256())
        )
        
        # Verify the signature
        result = SignatureVerificationService.verify_signature(
            photo_hash=sample_photo_hash,
            signature=signature,
            public_key=public_pem,
            algorithm="ECDSA-P256"
        )
        
        assert result is True

    def test_verify_signature_ecdsa_invalid(self, ecdsa_key_pair, sample_photo_hash):
        """Test ECDSA signature verification with invalid signature."""
        _, public_pem = ecdsa_key_pair
        
        # Use a fake signature
        fake_signature = b"invalid_signature_data"
        
        # Verify should fail
        result = SignatureVerificationService.verify_signature(
            photo_hash=sample_photo_hash,
            signature=fake_signature,
            public_key=public_pem,
            algorithm="ECDSA-P256"
        )
        
        assert result is False

    def test_verify_signature_wrong_algorithm(self, rsa_key_pair, sample_photo_hash):
        """Test signature verification with unsupported algorithm."""
        _, public_pem = rsa_key_pair
        
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            SignatureVerificationService.verify_signature(
                photo_hash=sample_photo_hash,
                signature=b"signature",
                public_key=public_pem,
                algorithm="INVALID-ALGO"
            )

    def test_verify_signature_wrong_key_type(self, rsa_key_pair, ecdsa_key_pair, sample_photo_hash):
        """Test signature verification with wrong key type."""
        rsa_private, _ = rsa_key_pair
        _, ecdsa_public_pem = ecdsa_key_pair
        
        # Sign with RSA but verify with ECDSA key
        signature = rsa_private.sign(
            sample_photo_hash,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        result = SignatureVerificationService.verify_signature(
            photo_hash=sample_photo_hash,
            signature=signature,
            public_key=ecdsa_public_pem,
            algorithm="RSA-2048"
        )
        
        assert result is False

    def test_validate_timestamp_valid(self):
        """Test timestamp validation with valid recent timestamp."""
        recent_timestamp = datetime.utcnow() - timedelta(minutes=2)
        
        result = SignatureVerificationService.validate_timestamp(
            timestamp=recent_timestamp,
            max_age_minutes=5
        )
        
        assert result is True

    def test_validate_timestamp_too_old(self):
        """Test timestamp validation with old timestamp."""
        old_timestamp = datetime.utcnow() - timedelta(minutes=10)
        
        result = SignatureVerificationService.validate_timestamp(
            timestamp=old_timestamp,
            max_age_minutes=5
        )
        
        assert result is False

    def test_validate_timestamp_future(self):
        """Test timestamp validation with future timestamp."""
        future_timestamp = datetime.utcnow() + timedelta(minutes=1)
        
        result = SignatureVerificationService.validate_timestamp(
            timestamp=future_timestamp,
            max_age_minutes=5
        )
        
        assert result is False

    def test_validate_timestamp_edge_case(self):
        """Test timestamp validation at exact max age."""
        edge_timestamp = datetime.utcnow() - timedelta(minutes=5)
        
        result = SignatureVerificationService.validate_timestamp(
            timestamp=edge_timestamp,
            max_age_minutes=5
        )
        
        assert result is True

    def test_validate_timestamp_invalid_type(self):
        """Test timestamp validation with invalid type."""
        result = SignatureVerificationService.validate_timestamp(
            timestamp="not a datetime",
            max_age_minutes=5
        )
        
        assert result is False

    def test_validate_location_hash_valid(self):
        """Test location hash validation with valid data."""
        sensor_data = {
            "gps_coords": (37.7749, -122.4194),
            "wifi_bssids": ["00:11:22:33:44:55", "AA:BB:CC:DD:EE:FF"],
            "cell_tower_ids": ["tower1", "tower2"]
        }
        salt = "test_salt"
        
        # Generate the expected hash
        from app.services.location_hash import LocationHashService
        expected_hash = LocationHashService.generate_location_hash(
            gps_coords=sensor_data["gps_coords"],
            wifi_bssids=sensor_data["wifi_bssids"],
            cell_tower_ids=sensor_data["cell_tower_ids"],
            salt=salt
        )
        
        # Validate
        result = SignatureVerificationService.validate_location_hash(
            sensor_data=sensor_data,
            location_hash=expected_hash,
            salt=salt
        )
        
        assert result is True

    def test_validate_location_hash_invalid(self):
        """Test location hash validation with invalid hash."""
        sensor_data = {
            "gps_coords": (37.7749, -122.4194),
            "wifi_bssids": ["00:11:22:33:44:55"],
            "cell_tower_ids": ["tower1"]
        }
        salt = "test_salt"
        
        # Use a fake hash
        fake_hash = "invalid_hash_value"
        
        # Validate should fail
        result = SignatureVerificationService.validate_location_hash(
            sensor_data=sensor_data,
            location_hash=fake_hash,
            salt=salt
        )
        
        assert result is False

    def test_validate_location_hash_missing_gps(self):
        """Test location hash validation with missing GPS data."""
        sensor_data = {
            "wifi_bssids": ["00:11:22:33:44:55"],
            "cell_tower_ids": ["tower1"]
        }
        salt = "test_salt"
        
        result = SignatureVerificationService.validate_location_hash(
            sensor_data=sensor_data,
            location_hash="some_hash",
            salt=salt
        )
        
        assert result is False

    def test_validate_location_hash_different_salt(self):
        """Test location hash validation with different salt."""
        sensor_data = {
            "gps_coords": (37.7749, -122.4194),
            "wifi_bssids": ["00:11:22:33:44:55"],
            "cell_tower_ids": ["tower1"]
        }
        
        # Generate hash with one salt
        from app.services.location_hash import LocationHashService
        hash_with_salt1 = LocationHashService.generate_location_hash(
            gps_coords=sensor_data["gps_coords"],
            wifi_bssids=sensor_data["wifi_bssids"],
            cell_tower_ids=sensor_data["cell_tower_ids"],
            salt="salt1"
        )
        
        # Validate with different salt
        result = SignatureVerificationService.validate_location_hash(
            sensor_data=sensor_data,
            location_hash=hash_with_salt1,
            salt="salt2"
        )
        
        assert result is False
