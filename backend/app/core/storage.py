"""
Storage service factory - provides the appropriate storage backend.

Supports:
- Mock storage (for testing)
- Cloudinary (for production on Render free tier)
- S3-compatible storage (AWS S3, MinIO, etc.)
"""
import os
from app.services.storage_interface import StorageInterface, MockStorageService


def get_storage_service() -> StorageInterface:
    """
    Get the appropriate storage service based on environment.

    Priority:
    1. TESTING or USE_MOCK_STORAGE -> MockStorageService
    2. CLOUDINARY_CLOUD_NAME set -> CloudinaryStorageService
    3. AWS credentials set -> S3StorageService
    4. Fallback -> MockStorageService
    """
    # Test/mock mode
    if os.getenv('TESTING') == 'true' or os.getenv('USE_MOCK_STORAGE') == 'true':
        return MockStorageService()

    # Cloudinary (preferred for Render deployment)
    if os.getenv('CLOUDINARY_CLOUD_NAME'):
        from app.services.cloudinary_storage import CloudinaryStorageService
        return CloudinaryStorageService()

    # S3-compatible storage
    from app.core.config import settings
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        from app.services.s3_storage import S3StorageService
        return S3StorageService()

    # Fallback to mock
    return MockStorageService()


# Global storage service instance (will be set by dependency injection)
storage_service: StorageInterface = None
