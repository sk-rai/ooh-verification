#!/usr/bin/env python3
"""Manual test of audit logging system."""

import sys
import uuid
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, '.')

from app.services.audit_logger import audit_logger, AuditFlag

def main():
    print("Testing Audit Logging System")
    print("=" * 50)
    
    # Test data
    vendor_id = "TEST01"
    photo_id = str(uuid.uuid4())
    campaign_code = "TESTCAMP"
    
    sensor_data = {
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
    
    signature = {
        'signature': 'base64_encoded_test_signature',
        'algorithm': 'SHA256withRSA',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    device_info = {
        'model': 'Pixel 6',
        'os_version': 'Android 13',
        'app_version': '1.0.0'
    }
    
    # Log first record
    print("\n1. Logging first audit record...")
    audit_id_1 = audit_logger.log_photo_capture(
        photo_id=photo_id,
        vendor_id=vendor_id,
        campaign_code=campaign_code,
        sensor_data=sensor_data,
        signature=signature,
        device_info=device_info,
        flags=[AuditFlag.LOW_GPS_ACCURACY]
    )
    
    if audit_id_1:
        print(f"   ✓ Created audit record: {audit_id_1}")
    else:
        print("   ✗ Failed to create audit record")
        return 1
    
    # Log second record
    print("\n2. Logging second audit record...")
    photo_id_2 = str(uuid.uuid4())
    audit_id_2 = audit_logger.log_photo_capture(
        photo_id=photo_id_2,
        vendor_id=vendor_id,
        campaign_code=campaign_code,
        sensor_data=sensor_data,
        signature=signature,
        device_info=device_info,
        flags=[]
    )
    
    if audit_id_2:
        print(f"   ✓ Created audit record: {audit_id_2}")
    else:
        print("   ✗ Failed to create audit record")
        return 1
    
    # Retrieve records
    print("\n3. Retrieving audit records...")
    record_1 = audit_logger.get_audit_record(audit_id_1)
    record_2 = audit_logger.get_audit_record(audit_id_2)
    
    if record_1 and record_2:
        print(f"   ✓ Retrieved both records")
        print(f"   - Record 1 previous_hash: {record_1.get('previous_record_hash')}")
        print(f"   - Record 2 previous_hash: {record_2.get('previous_record_hash')[:16]}...")
    else:
        print("   ✗ Failed to retrieve records")
        return 1
    
    # Verify chain integrity
    print("\n4. Verifying chain integrity...")
    is_valid, error = audit_logger.verify_chain_integrity(vendor_id)
    
    if is_valid:
        print(f"   ✓ Chain is valid")
    else:
        print(f"   ✗ Chain is invalid: {error}")
        return 1
    
    # Get vendor logs
    print("\n5. Retrieving vendor audit logs...")
    logs = audit_logger.get_vendor_audit_logs(vendor_id, limit=10)
    print(f"   ✓ Found {len(logs)} audit records for vendor {vendor_id}")
    
    print("\n" + "=" * 50)
    print("All tests passed! ✓")
    return 0

if __name__ == "__main__":
    sys.exit(main())
