# Audit Logging Quick Start Guide

## Prerequisites

- Python 3.8+
- Docker (for DynamoDB Local)
- boto3 installed (`pip install boto3`)

## Quick Setup (5 minutes)

### 1. Start DynamoDB Local

```bash
# Using Docker (recommended)
docker run -d -p 8000:8000 --name dynamodb-local amazon/dynamodb-local

# Verify it's running
curl http://localhost:8000
```

### 2. Set Environment Variables

Create or update `.env` file:

```bash
# DynamoDB Configuration
DYNAMODB_ENDPOINT_URL=http://localhost:8000
DYNAMODB_REGION=us-east-1
DYNAMODB_TABLE_NAME=trustcapture-audit-logs
```

### 3. Create Audit Table

```bash
cd backend
python scripts/create_audit_table.py
```

Expected output:
```
Creating DynamoDB table: trustcapture-audit-logs
Endpoint: http://localhost:8000
Region: us-east-1

✓ Successfully created table: trustcapture-audit-logs

Table schema:
  - Partition key: audit_id (String)
  - Sort key: timestamp (String)

Global Secondary Indexes:
  - vendor_id-timestamp-index
  - campaign_code-timestamp-index
```

### 4. Run Unit Tests

```bash
python -m pytest tests/test_audit_logger.py -v
```

Expected output:
```
tests/test_audit_logger.py::TestAuditRecordCreation::test_log_photo_capture_success PASSED
tests/test_audit_logger.py::TestAuditRecordCreation::test_log_photo_capture_with_no_flags PASSED
tests/test_audit_logger.py::TestAuditRecordCreation::test_log_photo_capture_with_multiple_flags PASSED
tests/test_audit_logger.py::TestHashChaining::test_first_record_has_no_previous_hash PASSED
tests/test_audit_logger.py::TestHashChaining::test_second_record_has_previous_hash PASSED
tests/test_audit_logger.py::TestHashChaining::test_hash_calculation_deterministic PASSED
tests/test_audit_logger.py::TestHashChaining::test_hash_changes_with_data PASSED
tests/test_audit_logger.py::TestChainIntegrityVerification::test_verify_empty_chain PASSED
tests/test_audit_logger.py::TestChainIntegrityVerification::test_verify_single_record_chain PASSED
tests/test_audit_logger.py::TestChainIntegrityVerification::test_verify_valid_chain PASSED
tests/test_audit_logger.py::TestChainIntegrityVerification::test_verify_broken_chain PASSED
... (more tests)

===================== 20+ passed in X.XXs =====================
```

### 5. Test Manually (Optional)

Create a test script `test_audit_manual.py`:

```python
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
```

Run the test:

```bash
cd backend
python test_audit_manual.py
```

Expected output:
```
Testing Audit Logging System
==================================================

1. Logging first audit record...
   ✓ Created audit record: 550e8400-e29b-41d4-a716-446655440000

2. Logging second audit record...
   ✓ Created audit record: 6ba7b810-9dad-11d1-80b4-00c04fd430c8

3. Retrieving audit records...
   ✓ Retrieved both records
   - Record 1 previous_hash: None
   - Record 2 previous_hash: a1b2c3d4e5f6g7h8...

4. Verifying chain integrity...
   ✓ Chain is valid

5. Retrieving vendor audit logs...
   ✓ Found 2 audit records for vendor TEST01

==================================================
All tests passed! ✓
```

## Verify DynamoDB Table

```bash
# List tables
aws dynamodb list-tables --endpoint-url http://localhost:8000

# Describe table
aws dynamodb describe-table \
  --table-name trustcapture-audit-logs \
  --endpoint-url http://localhost:8000

# Scan table (see all records)
aws dynamodb scan \
  --table-name trustcapture-audit-logs \
  --endpoint-url http://localhost:8000
```

## Troubleshooting

### DynamoDB Local Not Running

```bash
# Check if container is running
docker ps | grep dynamodb-local

# Start if stopped
docker start dynamodb-local

# Or restart
docker restart dynamodb-local
```

### Table Already Exists Error

```bash
# Delete table
aws dynamodb delete-table \
  --table-name trustcapture-audit-logs \
  --endpoint-url http://localhost:8000

# Recreate
python scripts/create_audit_table.py
```

### Connection Refused Error

```bash
# Check if DynamoDB Local is listening
curl http://localhost:8000

# Check Docker logs
docker logs dynamodb-local

# Restart Docker container
docker restart dynamodb-local
```

### Import Errors

```bash
# Install dependencies
pip install boto3 botocore

# Verify installation
python -c "import boto3; print(boto3.__version__)"
```

## Next Steps

1. **Integrate with Photo Upload API**: See `AUDIT_INTEGRATION.md`
2. **Test Integration**: Upload a photo and verify audit log
3. **Production Setup**: See `AUDIT_LOGGING.md` for AWS setup

## Cleanup

```bash
# Stop and remove DynamoDB Local
docker stop dynamodb-local
docker rm dynamodb-local

# Remove test data
aws dynamodb delete-table \
  --table-name trustcapture-audit-logs \
  --endpoint-url http://localhost:8000
```

## Resources

- **Full Documentation**: `AUDIT_LOGGING.md`
- **Integration Guide**: `AUDIT_INTEGRATION.md`
- **Implementation Summary**: `TASK13_IMPLEMENTATION_SUMMARY.md`
- **DynamoDB Local**: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html
