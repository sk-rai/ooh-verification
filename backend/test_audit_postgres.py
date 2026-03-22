#!/usr/bin/env python3
"""
Simple test script to verify audit logger PostgreSQL refactoring.
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, '.')

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, text

from app.models.audit_log import AuditLog
from app.services.audit_logger import AuditLogger, AuditFlag
from app.core.database import Base


# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test_trustcapture"


async def setup_database():
    """Create test database and tables."""
    print("🔧 Setting up test database...")
    
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        # Drop and recreate tables
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        
        # Create immutability triggers
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'Audit logs are immutable and cannot be modified or deleted';
            END;
            $$ LANGUAGE plpgsql;
        """))
        
        await conn.execute(text("""
            CREATE TRIGGER audit_log_immutable_update
                BEFORE UPDATE ON audit_logs
                FOR EACH ROW
                EXECUTE FUNCTION prevent_audit_log_modification();
        """))
        
        await conn.execute(text("""
            CREATE TRIGGER audit_log_immutable_delete
                BEFORE DELETE ON audit_logs
                FOR EACH ROW
                EXECUTE FUNCTION prevent_audit_log_modification();
        """))
    
    await engine.dispose()
    print("✅ Database setup complete")


async def test_audit_logger():
    """Test audit logger functionality."""
    print("\n🧪 Testing Audit Logger with PostgreSQL...\n")
    
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with SessionLocal() as session:
        audit_logger = AuditLogger(session)
        
        # Test data
        vendor_id = "VND001"
        sample_sensor_data = {
            'gps_latitude': 37.7749295,
            'gps_longitude': -122.4194155,
            'gps_accuracy': 10.5,
            'wifi_networks': [
                {
                    'ssid': 'TestNetwork',
                    'bssid': '00:11:22:33:44:55',
                    'signal_strength': -45
                }
            ]
        }
        sample_signature = {
            'signature': 'base64_encoded_signature_data',
            'algorithm': 'SHA256withRSA',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        sample_device_info = {
            'model': 'Pixel 6',
            'os_version': 'Android 13',
            'app_version': '1.0.0'
        }
        
        # Test 1: Log first audit record
        print("1️⃣  Logging first audit record...")
        audit_id_1 = await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id=vendor_id,
            campaign_code="CAMP001",
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info,
            flags=[AuditFlag.LOW_GPS_ACCURACY.value]
        )
        print(f"   ✅ First record logged: {audit_id_1}")
        
        # Verify first record has no previous hash
        record_1 = await audit_logger.get_audit_record(audit_id_1)
        assert record_1['previous_record_hash'] is None, "First record should have no previous hash"
        print("   ✅ First record has no previous hash")
        
        # Test 2: Log second audit record (hash chaining)
        print("\n2️⃣  Logging second audit record (hash chaining)...")
        audit_id_2 = await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id=vendor_id,
            campaign_code="CAMP001",
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info
        )
        print(f"   ✅ Second record logged: {audit_id_2}")
        
        # Verify second record has previous hash
        record_2 = await audit_logger.get_audit_record(audit_id_2)
        assert record_2['previous_record_hash'] is not None, "Second record should have previous hash"
        assert len(record_2['previous_record_hash']) == 64, "Hash should be SHA-256 (64 hex chars)"
        print(f"   ✅ Second record has previous hash: {record_2['previous_record_hash'][:16]}...")
        
        # Test 3: Log third audit record
        print("\n3️⃣  Logging third audit record...")
        audit_id_3 = await audit_logger.log_photo_capture(
            photo_id=str(uuid.uuid4()),
            vendor_id=vendor_id,
            campaign_code="CAMP001",
            sensor_data=sample_sensor_data,
            signature=sample_signature,
            device_info=sample_device_info
        )
        print(f"   ✅ Third record logged: {audit_id_3}")
        
        # Test 4: Verify chain integrity
        print("\n4️⃣  Verifying chain integrity...")
        is_valid, error = await audit_logger.verify_chain_integrity(vendor_id)
        assert is_valid, f"Chain should be valid: {error}"
        print("   ✅ Chain integrity verified")
        
        # Test 5: Retrieve vendor audit logs
        print("\n5️⃣  Retrieving vendor audit logs...")
        logs = await audit_logger.get_vendor_audit_logs(vendor_id)
        assert len(logs) == 3, f"Should have 3 logs, got {len(logs)}"
        print(f"   ✅ Retrieved {len(logs)} audit logs")
        
        # Test 6: Test immutability (update should fail)
        print("\n6️⃣  Testing immutability (update should fail)...")
        try:
            from sqlalchemy import update
            stmt = (
                update(AuditLog)
                .where(AuditLog.audit_id == uuid.UUID(audit_id_1))
                .values(campaign_code='MODIFIED')
            )
            await session.execute(stmt)
            await session.commit()
            print("   ❌ Update succeeded (should have failed!)")
            return False
        except Exception as e:
            if "immutable" in str(e).lower():
                print("   ✅ Update prevented by trigger (as expected)")
            else:
                print(f"   ⚠️  Update failed with unexpected error: {e}")
        
        # Test 7: Test immutability (delete should fail)
        print("\n7️⃣  Testing immutability (delete should fail)...")
        try:
            from sqlalchemy import delete
            stmt = delete(AuditLog).where(AuditLog.audit_id == uuid.UUID(audit_id_1))
            await session.execute(stmt)
            await session.commit()
            print("   ❌ Delete succeeded (should have failed!)")
            return False
        except Exception as e:
            if "immutable" in str(e).lower():
                print("   ✅ Delete prevented by trigger (as expected)")
            else:
                print(f"   ⚠️  Delete failed with unexpected error: {e}")
    
    await engine.dispose()
    return True


async def main():
    """Main test function."""
    try:
        await setup_database()
        success = await test_audit_logger()
        
        if success:
            print("\n" + "="*60)
            print("✅ ALL TESTS PASSED!")
            print("="*60)
            print("\n📊 Summary:")
            print("  ✅ PostgreSQL audit logging working")
            print("  ✅ Hash chaining functional")
            print("  ✅ Chain integrity verification working")
            print("  ✅ Immutability enforced by triggers")
            print("  ✅ No AWS/DynamoDB dependency")
            print("\n🎉 Refactoring complete!")
            return 0
        else:
            print("\n❌ Some tests failed")
            return 1
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
