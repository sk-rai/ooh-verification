"""
Storage service factory - provides the appropriate storage backend.

This allows easy switching between:
- Mock storage (for testing)
- S3-compatible storage (for production)
- Local filesystem storage (for simple deployments)
"""
import os
from app.services.storage_interface import StorageInterface, MockStorageService


def get_storage_service() -> StorageInterface:
    """
    Get the appropriate storage service based on environment.
    
    Returns:
        StorageInterface implementation
    """
    # Check if we're in test mode
    if os.getenv('TESTING') == 'true' or os.getenv('USE_MOCK_STORAGE') == 'true':
        return MockStorageService()
    
    # Otherwise, use S3 storage (lazy import to avoid connection on module load)
    from app.services.s3_storage import S3StorageService
    return S3StorageService()


# Global storage service instance (will be set by dependency injection)
storage_service: StorageInterface = None
