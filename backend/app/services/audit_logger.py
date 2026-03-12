"""
Audit logging service for photo capture events.

Requirements:
- Req 10.1: Log all photo capture events
- Req 10.2: Hash chaining for immutability
- Req 10.3: Tamper-evident audit trail
- Req 10.4: Include sensor data in audit logs
- Req 10.5: Append-only storage (enforced by PostgreSQL triggers)
- Req 10.6: Cryptographic integrity
- Req 10.7: Audit flags for security events
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.exc import SQLAlchemyError

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class AuditFlag(str, Enum):
    """Audit flags for security and integrity events."""
    ROOTED_DEVICE = "ROOTED_DEVICE"
    EMULATOR_MODE = "EMULATOR_MODE"
    LOW_GPS_ACCURACY = "LOW_GPS_ACCURACY"
    SAFETYNET_FAILED = "SAFETYNET_FAILED"
    OFFLINE_CAPTURE = "OFFLINE_CAPTURE"
    LOCATION_MISMATCH = "LOCATION_MISMATCH"


class AuditLogger:
    """Service for logging photo capture events to PostgreSQL with hash chaining."""

    def __init__(self, db: AsyncSession):
        """
        Initialize audit logger.
        
        Args:
            db: SQLAlchemy async session
        """
        self.db = db

    def _calculate_record_hash(self, record: Dict[str, Any]) -> str:
        """
        Calculate SHA-256 hash of audit record for chain integrity.

        Args:
            record: Audit record dictionary

        Returns:
            Hex string of SHA-256 hash
        """
        # Create deterministic string from record fields
        hash_data = {
            'audit_id': str(record['audit_id']),
            'timestamp': record['timestamp'].isoformat() if isinstance(record['timestamp'], datetime) else record['timestamp'],
            'vendor_id': record['vendor_id'],
            'photo_id': str(record['photo_id']),
            'campaign_code': record['campaign_code'],
            'sensor_data': record.get('sensor_data'),
            'signature': record.get('signature'),
            'previous_record_hash': record.get('previous_record_hash')
        }

        # Convert to JSON with sorted keys for determinism
        hash_string = json.dumps(hash_data, sort_keys=True, default=str)

        # Calculate SHA-256 hash
        return hashlib.sha256(hash_string.encode('utf-8')).hexdigest()

    async def _get_last_audit_record(self, vendor_id: str) -> Optional[AuditLog]:
        """
        Retrieve the last audit record for a vendor (for hash chaining).

        Args:
            vendor_id: Vendor identifier

        Returns:
            Last audit record or None if no records exist
        """
        try:
            stmt = (
                select(AuditLog)
                .where(AuditLog.vendor_id == vendor_id)
                .order_by(desc(AuditLog.timestamp))
                .limit(1)
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()

        except SQLAlchemyError as e:
            logger.error(f"Error retrieving last audit record: {e}")
            return None

    async def log_photo_capture(
        self,
        photo_id: str,
        vendor_id: str,
        campaign_code: str,
        sensor_data: Dict[str, Any],
        signature: Dict[str, Any],
        device_info: Dict[str, Any],
        tenant_id: Optional[uuid.UUID] = None,
        flags: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Log a photo capture event to PostgreSQL with hash chaining.

        Args:
            photo_id: UUID of the captured photo
            vendor_id: Vendor identifier
            campaign_code: Campaign code
            sensor_data: Sensor data dictionary (GPS, WiFi, cell towers, etc.)
            signature: Photo signature dictionary (signature, algorithm, timestamp)
            device_info: Device information (model, os_version, app_version)
            tenant_id: Optional tenant ID for multi-tenancy
            flags: Optional list of audit flags

        Returns:
            Audit ID (UUID) if successful, None if failed
        """
        try:
            # Generate audit ID
            audit_id = uuid.uuid4()

            # Get current timestamp
            timestamp = datetime.now(timezone.utc)

            # Get last record for hash chaining
            last_record = await self._get_last_audit_record(vendor_id)
            previous_record_hash = None

            if last_record:
                # Calculate hash of previous record
                record_dict = {
                    'audit_id': last_record.audit_id,
                    'timestamp': last_record.timestamp,
                    'vendor_id': last_record.vendor_id,
                    'photo_id': last_record.photo_id,
                    'campaign_code': last_record.campaign_code,
                    'sensor_data': last_record.sensor_data,
                    'signature': last_record.signature,
                    'previous_record_hash': last_record.previous_record_hash
                }
                previous_record_hash = self._calculate_record_hash(record_dict)

            # Create audit record dictionary for hash calculation
            audit_record_dict = {
                'audit_id': audit_id,
                'timestamp': timestamp,
                'vendor_id': vendor_id,
                'photo_id': uuid.UUID(photo_id) if isinstance(photo_id, str) else photo_id,
                'campaign_code': campaign_code,
                'sensor_data': sensor_data,
                'signature': signature,
                'previous_record_hash': previous_record_hash
            }

            # Calculate hash of current record
            current_record_hash = self._calculate_record_hash(audit_record_dict)

            # Create AuditLog model instance
            audit_log = AuditLog(
                audit_id=audit_id,
                tenant_id=tenant_id,
                timestamp=timestamp,
                vendor_id=vendor_id,
                photo_id=uuid.UUID(photo_id) if isinstance(photo_id, str) else photo_id,
                campaign_code=campaign_code,
                sensor_data=sensor_data,
                signature=signature,
                device_info=device_info,
                previous_record_hash=previous_record_hash,
                record_hash=current_record_hash,
                audit_flags=flags or []
            )

            # Add to session and commit
            self.db.add(audit_log)
            await self.db.commit()
            await self.db.refresh(audit_log)

            logger.info(
                f"Logged audit record: audit_id={audit_id}, "
                f"vendor_id={vendor_id}, photo_id={photo_id}"
            )

            return str(audit_id)

        except SQLAlchemyError as e:
            logger.error(f"Error logging audit record: {e}")
            await self.db.rollback()
            return None
        except Exception as e:
            logger.error(f"Unexpected error logging audit record: {e}")
            await self.db.rollback()
            return None

    async def verify_chain_integrity(
        self,
        vendor_id: str,
        limit: Optional[int] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Verify the integrity of the audit log chain for a vendor.

        Args:
            vendor_id: Vendor identifier
            limit: Optional limit on number of records to verify

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Query all records for vendor in chronological order
            stmt = (
                select(AuditLog)
                .where(AuditLog.vendor_id == vendor_id)
                .order_by(AuditLog.timestamp)
            )
            
            if limit:
                stmt = stmt.limit(limit)
            
            result = await self.db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return True, None  # No records to verify

            # Verify first record has no previous hash
            first_record = items[0]
            if first_record.previous_record_hash is not None:
                return False, f"First record has previous_record_hash: {first_record.audit_id}"

            # Verify chain integrity
            for i in range(1, len(items)):
                current_record = items[i]
                previous_record = items[i - 1]

                # Calculate hash of previous record
                record_dict = {
                    'audit_id': previous_record.audit_id,
                    'timestamp': previous_record.timestamp,
                    'vendor_id': previous_record.vendor_id,
                    'photo_id': previous_record.photo_id,
                    'campaign_code': previous_record.campaign_code,
                    'sensor_data': previous_record.sensor_data,
                    'signature': previous_record.signature,
                    'previous_record_hash': previous_record.previous_record_hash
                }
                expected_hash = self._calculate_record_hash(record_dict)
                actual_hash = current_record.previous_record_hash

                if expected_hash != actual_hash:
                    return False, (
                        f"Hash chain broken at record {current_record.audit_id}: "
                        f"expected {expected_hash}, got {actual_hash}"
                    )

            return True, None

        except SQLAlchemyError as e:
            logger.error(f"Error verifying chain integrity: {e}")
            return False, str(e)
        except Exception as e:
            logger.error(f"Unexpected error verifying chain integrity: {e}")
            return False, str(e)

    async def get_audit_record(self, audit_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific audit record by ID.

        Args:
            audit_id: Audit record ID

        Returns:
            Audit record dictionary or None if not found
        """
        try:
            stmt = select(AuditLog).where(AuditLog.audit_id == uuid.UUID(audit_id))
            result = await self.db.execute(stmt)
            audit_log = result.scalar_one_or_none()
            
            if not audit_log:
                return None
            
            return {
                'audit_id': str(audit_log.audit_id),
                'timestamp': audit_log.timestamp.isoformat(),
                'vendor_id': audit_log.vendor_id,
                'photo_id': str(audit_log.photo_id),
                'campaign_code': audit_log.campaign_code,
                'sensor_data': audit_log.sensor_data,
                'signature': audit_log.signature,
                'device_info': audit_log.device_info,
                'previous_record_hash': audit_log.previous_record_hash,
                'record_hash': audit_log.record_hash,
                'audit_flags': audit_log.audit_flags,
                'created_at': int(audit_log.created_at.timestamp())
            }

        except SQLAlchemyError as e:
            logger.error(f"Error retrieving audit record: {e}")
            return None

    async def get_vendor_audit_logs(
        self,
        vendor_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit logs for a vendor.

        Args:
            vendor_id: Vendor identifier
            limit: Maximum number of records to retrieve

        Returns:
            List of audit record dictionaries
        """
        try:
            stmt = (
                select(AuditLog)
                .where(AuditLog.vendor_id == vendor_id)
                .order_by(desc(AuditLog.timestamp))
                .limit(limit)
            )
            
            result = await self.db.execute(stmt)
            audit_logs = result.scalars().all()
            
            return [
                {
                    'audit_id': str(log.audit_id),
                    'timestamp': log.timestamp.isoformat(),
                    'vendor_id': log.vendor_id,
                    'photo_id': str(log.photo_id),
                    'campaign_code': log.campaign_code,
                    'sensor_data': log.sensor_data,
                    'signature': log.signature,
                    'device_info': log.device_info,
                    'previous_record_hash': log.previous_record_hash,
                    'record_hash': log.record_hash,
                    'audit_flags': log.audit_flags,
                    'created_at': int(log.created_at.timestamp())
                }
                for log in audit_logs
            ]

        except SQLAlchemyError as e:
            logger.error(f"Error retrieving vendor audit logs: {e}")
            return []
