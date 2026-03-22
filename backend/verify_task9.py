#!/usr/bin/env python3
"""Verification script for Task 9 implementation."""

import sys
from datetime import datetime, timedelta

print("=" * 60)
print("Task 9 Verification: Cryptographic Verification Services")
print("=" * 60)

# Test 1: Import services
print("\n1. Testing service imports...")
try:
    from backend.app.services.signature_verification import SignatureVerificationService
    from backend.app.services.location_hash import LocationHashService
    print("✓ Services imported successfully")
except Exception as e:
    print(f"✗ Failed to import services: {e}")
    sys.exit(1)

# Test 2: LocationHashService basic functionality
print("\n2. Testing LocationHashService...")
try:
    gps_coords = (37.7749, -122.4194)
    wifi_bssids = ["00:11:22:33:44:55", "AA:BB:CC:DD:EE:FF"]
    cell_tower_ids = ["tower1", "tower2"]
    salt = "test_salt"
    
    hash1 = LocationHashService.generate_location_hash(
        gps_coords=gps_coords,
        wifi_bssids=wifi_bssids,
        cell_tower_ids=cell_tower_ids,
        salt=salt
    )
    
    # Test determinism
    hash2 = LocationHashService.generate_location_hash(
        gps_coords=gps_coords,
        wifi_bssids=wifi_bssids,
        cell_tower_ids=cell_tower_ids,
        salt=salt
    )
    
    assert hash1 == hash2, "Hashes should be deterministic"
    assert len(hash1) == 64, "Hash should be 64 characters (SHA-256)"
    print(f"✓ LocationHashService working correctly")
    print(f"  Sample hash: {hash1[:32]}...")
except Exception as e:
    print(f"✗ LocationHashService failed: {e}")
    sys.exit(1)

# Test 3: SignatureVerificationService - timestamp validation
print("\n3. Testing SignatureVerificationService timestamp validation...")
try:
    # Valid timestamp
    recent = datetime.utcnow() - timedelta(minutes=2)
    assert SignatureVerificationService.validate_timestamp(recent, 5) is True
    
    # Old timestamp
    old = datetime.utcnow() - timedelta(minutes=10)
    assert SignatureVerificationService.validate_timestamp(old, 5) is False
    
    # Future timestamp
    future = datetime.utcnow() + timedelta(minutes=1)
    assert SignatureVerificationService.validate_timestamp(future, 5) is False
    
    print("✓ Timestamp validation working correctly")
except Exception as e:
    print(f"✗ Timestamp validation failed: {e}")
    sys.exit(1)

# Test 4: SignatureVerificationService - RSA signature verification
print("\n4. Testing RSA signature verification...")
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.backends import default_backend
    
    # Generate RSA key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    # Sign data
    photo_hash = b"test_photo_hash_data"
    signature = private_key.sign(
        photo_hash,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    # Verify signature
    result = SignatureVerificationService.verify_signature(
        photo_hash=photo_hash,
        signature=signature,
        public_key=public_pem,
        algorithm="RSA-2048"
    )
    
    assert result is True, "Valid RSA signature should verify"
    
    # Test invalid signature
    invalid_result = SignatureVerificationService.verify_signature(
        photo_hash=photo_hash,
        signature=b"invalid_signature",
        public_key=public_pem,
        algorithm="RSA-2048"
    )
    
    assert invalid_result is False, "Invalid signature should not verify"
    
    print("✓ RSA signature verification working correctly")
except Exception as e:
    print(f"✗ RSA signature verification failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: SignatureVerificationService - ECDSA signature verification
print("\n5. Testing ECDSA signature verification...")
try:
    from cryptography.hazmat.primitives.asymmetric import ec
    
    # Generate ECDSA key pair
    private_key = ec.generate_private_key(
        ec.SECP256R1(),
        backend=default_backend()
    )
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    # Sign data
    photo_hash = b"test_photo_hash_data"
    signature = private_key.sign(
        photo_hash,
        ec.ECDSA(hashes.SHA256())
    )
    
    # Verify signature
    result = SignatureVerificationService.verify_signature(
        photo_hash=photo_hash,
        signature=signature,
        public_key=public_pem,
        algorithm="ECDSA-P256"
    )
    
    assert result is True, "Valid ECDSA signature should verify"
    
    print("✓ ECDSA signature verification working correctly")
except Exception as e:
    print(f"✗ ECDSA signature verification failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Location hash validation
print("\n6. Testing location hash validation...")
try:
    sensor_data = {
        "gps_coords": (37.7749, -122.4194),
        "wifi_bssids": ["00:11:22:33:44:55"],
        "cell_tower_ids": ["tower1"]
    }
    salt = "test_salt"
    
    # Generate hash
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
    
    assert result is True, "Valid location hash should validate"
    
    # Test invalid hash
    invalid_result = SignatureVerificationService.validate_location_hash(
        sensor_data=sensor_data,
        location_hash="invalid_hash",
        salt=salt
    )
    
    assert invalid_result is False, "Invalid location hash should not validate"
    
    print("✓ Location hash validation working correctly")
except Exception as e:
    print(f"✗ Location hash validation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ All Task 9 verifications passed!")
print("=" * 60)
print("\nImplemented services:")
print("  - SignatureVerificationService")
print("    • verify_signature() - RSA-2048 and ECDSA-P256 support")
print("    • validate_timestamp() - Time-based validation")
print("    • validate_location_hash() - Location data validation")
print("  - LocationHashService")
print("    • generate_location_hash() - SHA-256 deterministic hashing")
print("\nTest files created:")
print("  - backend/tests/test_signature_verification.py")
print("  - backend/tests/test_location_hash.py")
