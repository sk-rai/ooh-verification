"""Unit tests for LocationHashService."""

import pytest
from app.services.location_hash import LocationHashService


class TestLocationHashService:
    """Test suite for LocationHashService."""

    def test_generate_location_hash_basic(self):
        """Test basic location hash generation."""
        gps_coords = (37.7749, -122.4194)
        wifi_bssids = ["00:11:22:33:44:55"]
        cell_tower_ids = ["tower1"]
        salt = "test_salt"
        
        result = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=wifi_bssids,
            cell_tower_ids=cell_tower_ids,
            salt=salt
        )
        
        # Should return a SHA-256 hash (64 hex characters)
        assert isinstance(result, str)
        assert len(result) == 64
        assert all(c in '0123456789abcdef' for c in result)

    def test_generate_location_hash_deterministic(self):
        """Test that hash generation is deterministic."""
        gps_coords = (37.7749, -122.4194)
        wifi_bssids = ["00:11:22:33:44:55", "AA:BB:CC:DD:EE:FF"]
        cell_tower_ids = ["tower1", "tower2"]
        salt = "test_salt"
        
        # Generate hash twice
        hash1 = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=wifi_bssids,
            cell_tower_ids=cell_tower_ids,
            salt=salt
        )
        
        hash2 = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=wifi_bssids,
            cell_tower_ids=cell_tower_ids,
            salt=salt
        )
        
        # Should be identical
        assert hash1 == hash2

    def test_generate_location_hash_different_gps(self):
        """Test that different GPS coordinates produce different hashes."""
        wifi_bssids = ["00:11:22:33:44:55"]
        cell_tower_ids = ["tower1"]
        salt = "test_salt"
        
        hash1 = LocationHashService.generate_location_hash(
            gps_coords=(37.7749, -122.4194),
            wifi_bssids=wifi_bssids,
            cell_tower_ids=cell_tower_ids,
            salt=salt
        )
        
        hash2 = LocationHashService.generate_location_hash(
            gps_coords=(37.7750, -122.4194),  # Slightly different
            wifi_bssids=wifi_bssids,
            cell_tower_ids=cell_tower_ids,
            salt=salt
        )
        
        assert hash1 != hash2

    def test_generate_location_hash_different_wifi(self):
        """Test that different WiFi BSSIDs produce different hashes."""
        gps_coords = (37.7749, -122.4194)
        cell_tower_ids = ["tower1"]
        salt = "test_salt"
        
        hash1 = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=["00:11:22:33:44:55"],
            cell_tower_ids=cell_tower_ids,
            salt=salt
        )
        
        hash2 = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=["AA:BB:CC:DD:EE:FF"],
            cell_tower_ids=cell_tower_ids,
            salt=salt
        )
        
        assert hash1 != hash2

    def test_generate_location_hash_different_cell_towers(self):
        """Test that different cell tower IDs produce different hashes."""
        gps_coords = (37.7749, -122.4194)
        wifi_bssids = ["00:11:22:33:44:55"]
        salt = "test_salt"
        
        hash1 = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=wifi_bssids,
            cell_tower_ids=["tower1"],
            salt=salt
        )
        
        hash2 = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=wifi_bssids,
            cell_tower_ids=["tower2"],
            salt=salt
        )
        
        assert hash1 != hash2

    def test_generate_location_hash_different_salt(self):
        """Test that different salts produce different hashes."""
        gps_coords = (37.7749, -122.4194)
        wifi_bssids = ["00:11:22:33:44:55"]
        cell_tower_ids = ["tower1"]
        
        hash1 = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=wifi_bssids,
            cell_tower_ids=cell_tower_ids,
            salt="salt1"
        )
        
        hash2 = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=wifi_bssids,
            cell_tower_ids=cell_tower_ids,
            salt="salt2"
        )
        
        assert hash1 != hash2

    def test_generate_location_hash_wifi_order_independence(self):
        """Test that WiFi BSSID order doesn't affect hash (sorted internally)."""
        gps_coords = (37.7749, -122.4194)
        cell_tower_ids = ["tower1"]
        salt = "test_salt"
        
        hash1 = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=["00:11:22:33:44:55", "AA:BB:CC:DD:EE:FF"],
            cell_tower_ids=cell_tower_ids,
            salt=salt
        )
        
        hash2 = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=["AA:BB:CC:DD:EE:FF", "00:11:22:33:44:55"],  # Reversed order
            cell_tower_ids=cell_tower_ids,
            salt=salt
        )
        
        # Should be the same due to internal sorting
        assert hash1 == hash2

    def test_generate_location_hash_cell_tower_order_independence(self):
        """Test that cell tower ID order doesn't affect hash (sorted internally)."""
        gps_coords = (37.7749, -122.4194)
        wifi_bssids = ["00:11:22:33:44:55"]
        salt = "test_salt"
        
        hash1 = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=wifi_bssids,
            cell_tower_ids=["tower1", "tower2", "tower3"],
            salt=salt
        )
        
        hash2 = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=wifi_bssids,
            cell_tower_ids=["tower3", "tower1", "tower2"],  # Different order
            salt=salt
        )
        
        # Should be the same due to internal sorting
        assert hash1 == hash2

    def test_generate_location_hash_empty_wifi(self):
        """Test hash generation with empty WiFi list."""
        gps_coords = (37.7749, -122.4194)
        cell_tower_ids = ["tower1"]
        salt = "test_salt"
        
        result = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=[],
            cell_tower_ids=cell_tower_ids,
            salt=salt
        )
        
        # Should still generate a valid hash
        assert isinstance(result, str)
        assert len(result) == 64

    def test_generate_location_hash_empty_cell_towers(self):
        """Test hash generation with empty cell tower list."""
        gps_coords = (37.7749, -122.4194)
        wifi_bssids = ["00:11:22:33:44:55"]
        salt = "test_salt"
        
        result = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=wifi_bssids,
            cell_tower_ids=[],
            salt=salt
        )
        
        # Should still generate a valid hash
        assert isinstance(result, str)
        assert len(result) == 64

    def test_generate_location_hash_gps_only(self):
        """Test hash generation with GPS coordinates only."""
        gps_coords = (37.7749, -122.4194)
        salt = "test_salt"
        
        result = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=[],
            cell_tower_ids=[],
            salt=salt
        )
        
        # Should still generate a valid hash
        assert isinstance(result, str)
        assert len(result) == 64

    def test_generate_location_hash_multiple_wifi(self):
        """Test hash generation with multiple WiFi BSSIDs."""
        gps_coords = (37.7749, -122.4194)
        wifi_bssids = [
            "00:11:22:33:44:55",
            "AA:BB:CC:DD:EE:FF",
            "11:22:33:44:55:66",
            "FF:EE:DD:CC:BB:AA"
        ]
        cell_tower_ids = ["tower1"]
        salt = "test_salt"
        
        result = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=wifi_bssids,
            cell_tower_ids=cell_tower_ids,
            salt=salt
        )
        
        # Should generate a valid hash
        assert isinstance(result, str)
        assert len(result) == 64

    def test_generate_location_hash_multiple_cell_towers(self):
        """Test hash generation with multiple cell tower IDs."""
        gps_coords = (37.7749, -122.4194)
        wifi_bssids = ["00:11:22:33:44:55"]
        cell_tower_ids = ["tower1", "tower2", "tower3", "tower4"]
        salt = "test_salt"
        
        result = LocationHashService.generate_location_hash(
            gps_coords=gps_coords,
            wifi_bssids=wifi_bssids,
            cell_tower_ids=cell_tower_ids,
            salt=salt
        )
        
        # Should generate a valid hash
        assert isinstance(result, str)
        assert len(result) == 64

    def test_generate_location_hash_precision(self):
        """Test that GPS coordinate precision is preserved in hash."""
        wifi_bssids = ["00:11:22:33:44:55"]
        cell_tower_ids = ["tower1"]
        salt = "test_salt"
        
        # Very close coordinates
        hash1 = LocationHashService.generate_location_hash(
            gps_coords=(37.774900, -122.419400),
            wifi_bssids=wifi_bssids,
            cell_tower_ids=cell_tower_ids,
            salt=salt
        )
        
        hash2 = LocationHashService.generate_location_hash(
            gps_coords=(37.774901, -122.419400),
            wifi_bssids=wifi_bssids,
            cell_tower_ids=cell_tower_ids,
            salt=salt
        )
        
        # Should be different due to precision
        assert hash1 != hash2
