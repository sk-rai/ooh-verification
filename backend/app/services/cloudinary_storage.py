"""
Cloudinary Storage Service for photo and thumbnail management.
Uses Cloudinary's free tier (25GB storage, 25GB bandwidth).
S3-compatible interface via StorageInterface.
"""
import cloudinary
import cloudinary.uploader
import cloudinary.api
from typing import Tuple
from PIL import Image
import io
import os
import logging

from app.services.storage_interface import StorageInterface

logger = logging.getLogger(__name__)


class CloudinaryStorageService(StorageInterface):
    """Storage service using Cloudinary for photo hosting."""

    def __init__(self):
        """Initialize Cloudinary with env vars."""
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True
        )
        logger.info("Cloudinary storage initialized (cloud: %s)", os.getenv("CLOUDINARY_CLOUD_NAME"))

    def upload_photo_with_thumbnail(
        self,
        photo_bytes: bytes,
        campaign_id: str,
        photo_id: str
    ) -> Tuple[str, str, str, str]:
        """Upload photo and thumbnail to Cloudinary."""
        # Upload original photo
        photo_public_id = f"trustcapture/photos/{campaign_id}/{photo_id}"
        photo_result = cloudinary.uploader.upload(
            photo_bytes,
            public_id=photo_public_id,
            resource_type="image",
            overwrite=True,
            folder="",  # public_id already has folder
        )
        photo_url = photo_result["secure_url"]
        photo_key = photo_result["public_id"]

        # Generate thumbnail URL using Cloudinary transformations (no extra upload needed)
        thumbnail_key = photo_key  # same asset
        thumbnail_url = cloudinary.utils.cloudinary_url(
            photo_key,
            width=200,
            height=200,
            crop="fill",
            quality="auto",
            format="jpg",
            secure=True
        )[0]

        return photo_key, photo_url, thumbnail_key, thumbnail_url

    def get_thumbnail_url(self, photo_key: str) -> str:
        """Get Cloudinary thumbnail URL with transformations."""
        url, _ = cloudinary.utils.cloudinary_url(
            photo_key,
            width=200,
            height=200,
            crop="fill",
            quality="auto",
            format="jpg",
            secure=True
        )
        return url

    def get_photo_url(self, photo_key: str) -> str:
        """Get Cloudinary URL for a photo."""
        url, _ = cloudinary.utils.cloudinary_url(photo_key, secure=True)
        return url

    def delete_photo(self, photo_key: str) -> bool:
        """Delete photo from Cloudinary."""
        try:
            result = cloudinary.uploader.destroy(photo_key)
            return result.get("result") == "ok"
        except Exception as e:
            logger.error(f"Failed to delete from Cloudinary: {e}")
            return False
