"""Location hash service for TrustCapture."""

import hashlib
from typing import List, Tuple


class LocationHashService:
    """Service for generating and validating location hashes."""

    @staticmethod
    def generate_location_hash(
        gps_coords: Tuple[float, float],
        wifi_bssids: List[str],
        cell_tower_ids: List[str],
        salt: str
    ) -> str:
        """
        Generate a deterministic hash from location sensor data.

        Args:
            gps_coords: Tuple of (latitude, longitude)
            wifi_bssids: List of WiFi BSSID strings
            cell_tower_ids: List of cell tower ID strings
            salt: Salt string for hashing

        Returns:
            str: SHA-256 hash of the location data
        """
        # Build a deterministic string from all sensor data
        data_parts = []

        # Add GPS coordinates
        if gps_coords:
            lat, lon = gps_coords
            data_parts.append(f"gps:{lat},{lon}")

        # Add WiFi BSSIDs (sorted for determinism)
        if wifi_bssids:
            sorted_bssids = sorted(wifi_bssids)
            data_parts.append(f"wifi:{','.join(sorted_bssids)}")

        # Add cell tower IDs (sorted for determinism)
        if cell_tower_ids:
            sorted_towers = sorted(cell_tower_ids)
            data_parts.append(f"cell:{','.join(sorted_towers)}")

        # Add salt
        data_parts.append(f"salt:{salt}")

        # Combine all parts
        data_string = "|".join(data_parts)

        # Generate SHA-256 hash
        hash_obj = hashlib.sha256(data_string.encode('utf-8'))
        return hash_obj.hexdigest()
