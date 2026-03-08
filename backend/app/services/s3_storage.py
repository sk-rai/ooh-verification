"""
S3 Storage Service for photo and thumbnail management.

Uses boto3 for AWS S3 integration with LocalStack support for development.
"""
import boto3
from botocore.exceptions import ClientError
from PIL import Image
import io
from typing import Optional, Tuple
import uuid
from datetime import datetime

from app.core.config import settings


class S3StorageService:
    """Service for managing photo storage in S3."""

    def __init__(self):
        """Initialize S3 client with LocalStack support for development."""
        # Use LocalStack for development if AWS credentials not provided
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            self.use_localstack = False
        else:
            # LocalStack configuration for development
            self.s3_client = boto3.client(
                's3',
                endpoint_url='http://localhost:4566',  # LocalStack default endpoint
                aws_access_key_id='test',
                aws_secret_access_key='test',
                region_name=settings.AWS_REGION
            )
            self.use_localstack = True

        self.bucket_name = settings.S3_BUCKET_NAME or 'trustcapture-photos-dev'
        self.thumbnail_bucket = settings.S3_THUMBNAIL_BUCKET or 'trustcapture-thumbnails-dev'

        # Ensure buckets exist in development
        if self.use_localstack:
            self._ensure_buckets_exist()

    def _ensure_buckets_exist(self):
        """Ensure S3 buckets exist (for LocalStack development)."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except ClientError:
            try:
                self.s3_client.create_bucket(Bucket=self.bucket_name)
                # Enable versioning for tamper protection
                self.s3_client.put_bucket_versioning(
                    Bucket=self.bucket_name,
                    VersioningConfiguration={'Status': 'Enabled'}
                )
            except Exception as e:
                print(f"Warning: Could not create bucket {self.bucket_name}: {e}")

        try:
            self.s3_client.head_bucket(Bucket=self.thumbnail_bucket)
        except ClientError:
            try:
                self.s3_client.create_bucket(Bucket=self.thumbnail_bucket)
            except Exception as e:
                print(f"Warning: Could not create bucket {self.thumbnail_bucket}: {e}")

    def generate_s3_key(self, campaign_id: str, photo_id: str, is_thumbnail: bool = False) -> str:
        """
        Generate unique S3 key for photo or thumbnail.

        Args:
            campaign_id: Campaign UUID
            photo_id: Photo UUID
            is_thumbnail: Whether this is a thumbnail

        Returns:
            S3 key path
        """
        prefix = "thumbnails" if is_thumbnail else "photos"
        timestamp = datetime.utcnow().strftime("%Y/%m/%d")
        return f"{prefix}/{campaign_id}/{timestamp}/{photo_id}.jpg"

    def upload_photo(self, photo_bytes: bytes, s3_key: str) -> str:
        """
        Upload photo to S3.

        Args:
            photo_bytes: Photo file bytes
            s3_key: S3 key path

        Returns:
            S3 URL or key

        Raises:
            Exception: If upload fails
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=photo_bytes,
                ContentType='image/jpeg',
                Metadata={
                    'uploaded_at': datetime.utcnow().isoformat()
                }
            )

            # Return URL or key based on environment
            if self.use_localstack:
                return f"http://localhost:4566/{self.bucket_name}/{s3_key}"
            else:
                return f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"

        except ClientError as e:
            raise Exception(f"Failed to upload photo to S3: {str(e)}")

    def generate_thumbnail(self, photo_bytes: bytes, size: Tuple[int, int] = (200, 200)) -> bytes:
        """
        Generate thumbnail from photo bytes.

        Args:
            photo_bytes: Original photo bytes
            size: Thumbnail size (width, height)

        Returns:
            Thumbnail bytes

        Raises:
            Exception: If thumbnail generation fails
        """
        try:
            # Open image from bytes
            image = Image.open(io.BytesIO(photo_bytes))

            # Convert to RGB if necessary (handles RGBA, etc.)
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Generate thumbnail (maintains aspect ratio)
            image.thumbnail(size, Image.Resampling.LANCZOS)

            # Save to bytes
            thumbnail_io = io.BytesIO()
            image.save(thumbnail_io, format='JPEG', quality=85, optimize=True)
            thumbnail_io.seek(0)

            return thumbnail_io.read()

        except Exception as e:
            raise Exception(f"Failed to generate thumbnail: {str(e)}")

    def upload_thumbnail(self, thumbnail_bytes: bytes, s3_key: str) -> str:
        """
        Upload thumbnail to S3.

        Args:
            thumbnail_bytes: Thumbnail file bytes
            s3_key: S3 key path

        Returns:
            S3 URL or key

        Raises:
            Exception: If upload fails
        """
        try:
            self.s3_client.put_object(
                Bucket=self.thumbnail_bucket,
                Key=s3_key,
                Body=thumbnail_bytes,
                ContentType='image/jpeg',
                Metadata={
                    'uploaded_at': datetime.utcnow().isoformat()
                }
            )

            # Return URL or key based on environment
            if self.use_localstack:
                return f"http://localhost:4566/{self.thumbnail_bucket}/{s3_key}"
            else:
                return f"https://{self.thumbnail_bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"

        except ClientError as e:
            raise Exception(f"Failed to upload thumbnail to S3: {str(e)}")

    def upload_photo_with_thumbnail(
        self,
        photo_bytes: bytes,
        campaign_id: str,
        photo_id: str
    ) -> Tuple[str, str, str, str]:
        """
        Upload photo and generate/upload thumbnail.

        Args:
            photo_bytes: Photo file bytes
            campaign_id: Campaign UUID
            photo_id: Photo UUID

        Returns:
            Tuple of (photo_s3_key, photo_url, thumbnail_s3_key, thumbnail_url)

        Raises:
            Exception: If upload fails
        """
        # Generate S3 keys
        photo_s3_key = self.generate_s3_key(campaign_id, photo_id, is_thumbnail=False)
        thumbnail_s3_key = self.generate_s3_key(campaign_id, photo_id, is_thumbnail=True)

        # Upload photo
        photo_url = self.upload_photo(photo_bytes, photo_s3_key)

        # Generate and upload thumbnail
        thumbnail_bytes = self.generate_thumbnail(photo_bytes)
        thumbnail_url = self.upload_thumbnail(thumbnail_bytes, thumbnail_s3_key)

        return photo_s3_key, photo_url, thumbnail_s3_key, thumbnail_url

    def delete_photo(self, s3_key: str) -> bool:
        """
        Delete photo from S3.

        Args:
            s3_key: S3 key path

        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return True
        except ClientError as e:
            print(f"Failed to delete photo from S3: {str(e)}")
            return False

    def delete_thumbnail(self, s3_key: str) -> bool:
        """
        Delete thumbnail from S3.

        Args:
            s3_key: S3 key path

        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.thumbnail_bucket,
                Key=s3_key
            )
            return True
        except ClientError as e:
            print(f"Failed to delete thumbnail from S3: {str(e)}")
            return False


# Singleton instance
s3_storage_service = S3StorageService()
