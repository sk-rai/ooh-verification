"""
Photo Signature model - stores cryptographic signatures for tamper detection.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class PhotoSignature(Base):
    """
    Photo Signature model - cryptographic signatures for photo integrity.
    
    Requirements:
    - Req 8.1-8.7: Cryptographic photo signing
    - Req 27.1-27.6: Photo signature verification
    - Req 28.1-28.5: Location hash collision resistance
    - Property 3: Photo signature verification inverse
    - Property 4: Location hash determinism
    - Property 5: Location hash uniqueness
    - Property 13: Photo signature tamper detection
    """
    __tablename__ = "photo_signatures"

    # Primary Key
    signature_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Photo Association
    photo_id = Column(
        UUID(as_uuid=True),
        ForeignKey("photos.photo_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One signature per photo
        index=True
    )
    
    # Signature Data
    signature_data = Column(String, nullable=False)  # Base64 encoded signature
    algorithm = Column(String(50), nullable=False)  # 'SHA256withRSA' or 'SHA256withECDSA'
    
    # Device Information
    device_id = Column(String(255), nullable=False)  # Android device identifier
    
    # Signature Metadata
    timestamp = Column(DateTime, nullable=False)  # When signature was generated
    location_hash = Column(String(64), nullable=False)  # SHA-256 hash of sensor data
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    photo = relationship("Photo", back_populates="signature")

    def __repr__(self):
        return (
            f"<PhotoSignature(signature_id={self.signature_id}, "
            f"photo_id={self.photo_id}, algorithm={self.algorithm})>"
        )
