"""
Storage interface for photo and thumbnail management.

This interface allows easy switching between storage backends:
- S3-compatible storage (AWS S3, MinIO, Backblaze B2, Wasabi, etc.)
- Local filesystem storage
- Mock storage for testing
"""
from abc import ABC, abstractmethod
from typing import Tuple


class StorageInterface(ABC):
    """Abstract interface for photo storage."""

    @abstractmethod
    def upload_photo_with_thumbnail(
        self,
        photo_bytes: bytes,
        campaign_id: str,
        photo_id: str
    ) -> Tuple[str, str, str, str]:
        """
        Upload photo and generate thumbnail.

        Args:
            photo_bytes: Photo file bytes
            campaign_id: Campaign identifier
            photo_id: Photo identifier

        Returns:
            Tuple of (photo_key, photo_url, thumbnail_key, thumbnail_url)
        """
        pass

    @abstractmethod
    def get_photo_url(self, photo_key: str) -> str:
        """
        Get URL for accessing a photo.

        Args:
            photo_key: Photo storage key

        Returns:
            URL to access the photo
        """
        pass

    @abstractmethod
    def delete_photo(self, photo_key: str) -> bool:
        """
        Delete a photo from storage.

        Args:
            photo_key: Photo storage key

        Returns:
            True if deleted successfully
        """
        pass


class MockStorageService(StorageInterface):
    """Mock storage service for testing (no external dependencies)."""

    def __init__(self):
        """Initialize mock storage."""
        self.stored_photos = {}  # key -> bytes
        self.stored_thumbnails = {}  # key -> bytes

    def upload_photo_with_thumbnail(
        self,
        photo_bytes: bytes,
        campaign_id: str,
        photo_id: str
    ) -> Tuple[str, str, str, str]:
        """Upload photo and thumbnail to memory."""
        # Generate keys
        photo_key = f"photos/{campaign_id}/{photo_id}.jpg"
        thumbnail_key = f"thumbnails/{campaign_id}/{photo_id}_thumb.jpg"

        # Store in memory
        self.stored_photos[photo_key] = photo_bytes
        
        # Generate mock thumbnail (just store original for testing)
        self.stored_thumbnails[thumbnail_key] = photo_bytes[:1000]  # Mock thumbnail

        # Generate mock URLs
        photo_url = f"http://mock-storage.local/{photo_key}"
        thumbnail_url = f"http://mock-storage.local/{thumbnail_key}"

        return photo_key, photo_url, thumbnail_key, thumbnail_url

    def get_photo_url(self, photo_key: str) -> str:
        """Get mock URL for photo."""
        return f"http://mock-storage.local/{photo_key}"

    def delete_photo(self, photo_key: str) -> bool:
        """Delete photo from memory."""
        if photo_key in self.stored_photos:
            del self.stored_photos[photo_key]
            return True
        return False
