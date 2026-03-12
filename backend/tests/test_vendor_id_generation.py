"""
Unit tests for vendor ID generation.

**Validates: Requirements 1.1, 12.1**
"""
import pytest
import re
from app.core.security import generate_vendor_id


class TestVendorIDGeneration:
    """
    Test vendor ID generation functionality.
    
    Requirements:
        - Req 1.1: Vendor ID generation (6-char alphanumeric)
        - Req 12.1: ID format validation
    """
    
    def test_vendor_id_format(self):
        """
        Test that generated vendor IDs match the expected format.
        
        Format: 6 characters, uppercase alphanumeric (A-Z, 0-9)
        """
        vendor_id = generate_vendor_id()
        
        # Check length
        assert len(vendor_id) == 6, f"Vendor ID should be 6 characters, got {len(vendor_id)}"
        
        # Check format (uppercase letters and digits only)
        pattern = r'^[A-Z0-9]{6}$'
        assert re.match(pattern, vendor_id), f"Vendor ID '{vendor_id}' does not match pattern {pattern}"
    
    def test_vendor_id_uniqueness(self):
        """
        Test that generated vendor IDs are unique across multiple generations.
        
        Note: This is a probabilistic test. With 36^6 possible IDs,
        collisions are extremely unlikely in small samples.
        """
        num_ids = 1000
        generated_ids = set()
        
        for _ in range(num_ids):
            vendor_id = generate_vendor_id()
            generated_ids.add(vendor_id)
        
        # All IDs should be unique
        assert len(generated_ids) == num_ids, \
            f"Expected {num_ids} unique IDs, got {len(generated_ids)}"
    
    def test_vendor_id_character_set(self):
        """
        Test that vendor IDs only contain valid characters.
        
        Valid characters: A-Z (uppercase) and 0-9
        """
        vendor_id = generate_vendor_id()
        valid_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
        
        for char in vendor_id:
            assert char in valid_chars, \
                f"Invalid character '{char}' in vendor ID '{vendor_id}'"
    
    def test_vendor_id_no_lowercase(self):
        """
        Test that vendor IDs do not contain lowercase letters.
        """
        vendor_id = generate_vendor_id()
        
        assert vendor_id.isupper() or vendor_id.isdigit() or all(c.isupper() or c.isdigit() for c in vendor_id), \
            f"Vendor ID '{vendor_id}' contains lowercase letters"
    
    def test_vendor_id_multiple_generations(self):
        """
        Test that multiple calls to generate_vendor_id() produce valid IDs.
        """
        pattern = r'^[A-Z0-9]{6}$'
        
        for _ in range(100):
            vendor_id = generate_vendor_id()
            assert re.match(pattern, vendor_id), \
                f"Generated invalid vendor ID: '{vendor_id}'"
