"""
Unit tests for audit logging system.

Requirements:
- Req 10.1: Log all photo capture events
- Req 10.2: Hash chaining for immutability
- Req 10.3: Tamper-evident audit trail
- Req 10.4: Include sensor data in audit logs
- Req 10.5: Append-only storage (enforced by PostgreSQL triggers)
- Req 10.6: Cryptographic integrity
- Req 10.7: Audit flags for security events
"""
import pytest
from datetime import datetime, timezone
import uuid

from sqlalchemy import select, update, delete
from sqlalchemy.exc import DatabaseError

from app.services.audit_logger import AuditLogger, AuditFlag
from app.models.audit_log import AuditLog


@pytest.fixture
def audit_logger(db_session):
    """Create audit logger with database session."""
    return AuditLogger(db_session)


@pytest.fixture
def sample_sensor_data():
    """Sample sensor data for testing."""
    return {
        'gps_latitude': 37.7749295,
        'gps_longitude': -122.4194155,
        'gps_accuracy': 10.5,
        'wifi_networks': [
            {
                'ssid': 'TestNetwork',
                'bssid': '00:11:22:33:44:55',
                'signal_strength': -45
            }
        ],
        'cell_towers': [
            {
                'cell_id': 12345,
                'lac': 100,
                'signal_strength': -75
            }
        ]
    }


@pytest.fixture
def sample_signature():
    """Sample signature data for testing."""
    return {
        'signature': 'base64_encoded_signature_data',
        'algorithm': 'SHA256withRSA',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


@pytest.fixture
def sample_device_info():
    """Sample device info for testing."""
    return {
        'model': 'Pixel 6',
        'os_version': 'Android 13',
        'app_version': '1.0.0'
    }


class TestAuditRecordCreation:
    """Test audit record creation and storage."""

    @pytest.mark.asyncio
    async def test_log_photo_capture_success(
        self,
        audit_logger,
        db_session,
        test_tenant,
        sample_sensor_data,
        sample_signature,
        sample_device_info
    ):
        """Test successful photo capture logging."""
        # Log photo capture
        photo_id = str(uuid.uuid4())
        vendor_id = "VND001"
        campaign_code = "CAMP001"

        audit_id = await audit_logger.log_photo_capture(
            photo_id=photo_id,
            vendor_id=vendor_id,
            campaign_code=campaign_code,
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
        )

        # Verify audit ID was returned
        assert audit_id is not None
        assert isinstance(audit_id, str)

        # Verify record was stored in database
        stmt = select(AuditLog).where(AuditLog.audit_id == uuid.UUID(audit_id))
        result = await db_session.execute(stmt)
        audit_log = result.scalar_one_or_none()

        assert audit_log is not None
        assert audit_log.vendor_id == vendor_id
        assert str(audit_log.photo_id) == photo_id
        assert audit_log.campaign_code == campaign_code
        assert audit_log.sensor_data == sample_sensor_data
        assert audit_log.signature == sample_signature
        assert audit_log.device_info == sample_device_info
        assert audit_log.previous_record_hash is None  # First record
        assert audit_log.record_hash is not None
        assert audit_log.audit_flags == []

    @pytest.mark.asyncio
    async def test_log_photo_capture_without_flags(
        self,
        audit_logger,
        db_session,
        test_tenant,
        sample_sensor_data,
        sample_signature,
        sample_device_info
    ):
        """Test logging without audit flags."""
        audit_id = await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id="VND001",
            campaign_code="CAMP001",
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
        )

        assert audit_id is not None

        stmt = select(AuditLog).where(AuditLog.audit_id == uuid.UUID(audit_id))
        result = await db_session.execute(stmt)
        audit_log = result.scalar_one_or_none()
        assert audit_log.audit_flags == []

    @pytest.mark.asyncio
    async def test_log_photo_capture_with_flags(
        self,
        audit_logger,
        db_session,
        test_tenant,
        sample_sensor_data,
        sample_signature,
        sample_device_info
    ):
        """Test logging with multiple audit flags."""
        flags = [
            AuditFlag.ROOTED_DEVICE.value,
            AuditFlag.LOW_GPS_ACCURACY.value
        ]

        audit_id = await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id="VND001",
            campaign_code="CAMP001",
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
            flags=flags
        )

        assert audit_id is not None

        stmt = select(AuditLog).where(AuditLog.audit_id == uuid.UUID(audit_id))
        result = await db_session.execute(stmt)
        audit_log = result.scalar_one_or_none()
        assert audit_log.audit_flags == flags


class TestHashChaining:
    """Test hash chaining functionality."""

    @pytest.mark.asyncio
    async def test_first_record_no_previous_hash(
        self,
        audit_logger,
        db_session,
        test_tenant,
        sample_sensor_data,
        sample_signature,
        sample_device_info
    ):
        """Test that first record has no previous hash."""
        audit_id = await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id="VND001",
            campaign_code="CAMP001",
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
        )

        stmt = select(AuditLog).where(AuditLog.audit_id == uuid.UUID(audit_id))
        result = await db_session.execute(stmt)
        audit_log = result.scalar_one_or_none()

        assert audit_log.previous_record_hash is None

    @pytest.mark.asyncio
    async def test_second_record_has_previous_hash(
        self,
        audit_logger,
        db_session,
        test_tenant,
        sample_sensor_data,
        sample_signature,
        sample_device_info
    ):
        """Test that second record links to first via hash."""
        vendor_id = "VND001"

        # Log first record
        first_audit_id = await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id=vendor_id,
            campaign_code="CAMP001",
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
        )

        # Log second record
        second_audit_id = await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id=vendor_id,
            campaign_code="CAMP001",
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
        )

        # Verify second record has previous hash
        stmt = select(AuditLog).where(AuditLog.audit_id == uuid.UUID(second_audit_id))
        result = await db_session.execute(stmt)
        second_log = result.scalar_one_or_none()

        assert second_log.previous_record_hash is not None
        assert len(second_log.previous_record_hash) == 64  # SHA-256 hex length


class TestChainIntegrityVerification:
    """Test audit log chain integrity verification."""

    @pytest.mark.asyncio
    async def test_verify_empty_chain(self, audit_logger, db_session):
        """Test verification of empty chain."""
        is_valid, error = await audit_logger.verify_chain_integrity('VND001')

        assert is_valid is True
        assert error is None

    @pytest.mark.asyncio
    async def test_verify_single_record_chain(
        self,
        audit_logger,
        db_session,
        test_tenant,
        sample_sensor_data,
        sample_signature,
        sample_device_info
    ):
        """Test verification of single record chain."""
        await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id='VND001',
            campaign_code='CAMP001',
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
        )

        is_valid, error = await audit_logger.verify_chain_integrity('VND001')

        assert is_valid is True
        assert error is None

    @pytest.mark.asyncio
    async def test_verify_multi_record_chain(
        self,
        audit_logger,
        db_session,
        test_tenant,
        sample_sensor_data,
        sample_signature,
        sample_device_info
    ):
        """Test verification of multi-record chain."""
        vendor_id = 'VND001'

        # Create chain of 3 records
        for i in range(3):
            await audit_logger.log_photo_capture(
                photo_id=str(uuid.uuid4()),
                vendor_id=vendor_id,
                campaign_code='CAMP001',
                sensor_data=sample_sensor_data,
                signature=sample_signature,
                device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
            )

        is_valid, error = await audit_logger.verify_chain_integrity(vendor_id)

        assert is_valid is True
        assert error is None

    @pytest.mark.asyncio
    async def test_verify_broken_chain(
        self,
        audit_logger,
        db_session,
        test_tenant,
        sample_sensor_data,
        sample_signature,
        sample_device_info
    ):
        """Test detection of broken chain."""
        vendor_id = 'VND001'

        # Create chain of 2 records
        await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id=vendor_id,
            campaign_code='CAMP001',
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
        )

        second_audit_id = await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id=vendor_id,
            campaign_code='CAMP001',
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
        )

        # Manually corrupt the chain by updating previous_record_hash
        # Note: This will fail due to immutability trigger, but we test the detection logic
        stmt = select(AuditLog).where(AuditLog.audit_id == uuid.UUID(second_audit_id))
        result = await db_session.execute(stmt)
        second_log = result.scalar_one_or_none()

        # Temporarily modify in memory for testing
        original_hash = second_log.previous_record_hash
        second_log.previous_record_hash = "corrupted_hash"

        is_valid, error = await audit_logger.verify_chain_integrity(vendor_id)

        # Restore original hash
        second_log.previous_record_hash = original_hash

        assert is_valid is False
        assert "Hash chain broken" in error


class TestAuditRecordRetrieval:
    """Test audit record retrieval operations."""

    @pytest.mark.asyncio
    async def test_get_audit_record_success(
        self,
        audit_logger,
        db_session,
        test_tenant,
        sample_sensor_data,
        sample_signature,
        sample_device_info
    ):
        """Test successful retrieval of audit record."""
        audit_id = await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id='VND001',
            campaign_code='CAMP001',
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
        )

        record = await audit_logger.get_audit_record(audit_id)

        assert record is not None
        assert record['audit_id'] == audit_id
        assert record['vendor_id'] == 'VND001'

    @pytest.mark.asyncio
    async def test_get_audit_record_not_found(self, audit_logger, db_session):
        """Test retrieval of non-existent record."""
        record = await audit_logger.get_audit_record(str(uuid.uuid4()))

        assert record is None

    @pytest.mark.asyncio
    async def test_get_vendor_audit_logs(
        self,
        audit_logger,
        db_session,
        test_tenant,
        sample_sensor_data,
        sample_signature,
        sample_device_info
    ):
        """Test retrieval of vendor audit logs."""
        vendor_id = 'VND001'

        # Create 3 audit logs
        for i in range(3):
            await audit_logger.log_photo_capture(
                photo_id=str(uuid.uuid4()),
                vendor_id=vendor_id,
                campaign_code='CAMP001',
                sensor_data=sample_sensor_data,
                signature=sample_signature,
                device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
            )

        logs = await audit_logger.get_vendor_audit_logs(vendor_id)

        assert len(logs) == 3
        assert all(log['vendor_id'] == vendor_id for log in logs)


class TestTimestampFormats:
    """Test timestamp format requirements."""

    @pytest.mark.asyncio
    async def test_timestamp_iso8601_format(
        self,
        audit_logger,
        db_session,
        test_tenant,
        sample_sensor_data,
        sample_signature,
        sample_device_info
    ):
        """Test that timestamps are in ISO 8601 format."""
        audit_id = await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id='VND001',
            campaign_code='CAMP001',
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
        )

        record = await audit_logger.get_audit_record(audit_id)

        # Verify ISO 8601 format
        timestamp = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
        assert timestamp is not None

    @pytest.mark.asyncio
    async def test_created_at_unix_timestamp(
        self,
        audit_logger,
        db_session,
        test_tenant,
        sample_sensor_data,
        sample_signature,
        sample_device_info
    ):
        """Test that created_at is a Unix timestamp."""
        audit_id = await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id='VND001',
            campaign_code='CAMP001',
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
        )

        record = await audit_logger.get_audit_record(audit_id)

        # Verify Unix timestamp
        assert isinstance(record['created_at'], int)
        assert record['created_at'] > 0


class TestImmutability:
    """Test immutability enforcement via PostgreSQL triggers."""

    @pytest.mark.asyncio
    async def test_update_audit_log_fails(
        self,
        audit_logger,
        db_session,
        test_tenant,
        sample_sensor_data,
        sample_signature,
        sample_device_info
    ):
        """Test that updating audit logs is prevented by trigger."""
        audit_id = await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id='VND001',
            campaign_code='CAMP001',
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
        )

        # Attempt to update the record
        with pytest.raises(DatabaseError) as exc_info:
            stmt = (
                update(AuditLog)
                .where(AuditLog.audit_id == uuid.UUID(audit_id))
                .values(campaign_code='MODIFIED')
            )
            await db_session.execute(stmt)
            await db_session.commit()

        assert "immutable" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_delete_audit_log_fails(
        self,
        audit_logger,
        db_session,
        test_tenant,
        sample_sensor_data,
        sample_signature,
        sample_device_info
    ):
        """Test that deleting audit logs is prevented by trigger."""
        audit_id = await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id='VND001',
            campaign_code='CAMP001',
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            tenant_id=test_tenant.tenant_id,
        )

        # Attempt to delete the record
        with pytest.raises(DatabaseError) as exc_info:
            stmt = delete(AuditLog).where(AuditLog.audit_id == uuid.UUID(audit_id))
            await db_session.execute(stmt)
            await db_session.commit()

        assert "immutable" in str(exc_info.value).lower()
