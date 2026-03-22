# Audit Logging System

## Overview

The TrustCapture audit logging system provides tamper-evident, immutable logging of all photo capture events using DynamoDB with cryptographic hash chaining.

## Requirements

**Validates Requirements:**
- Req 10.1: Log all photo capture events
- Req 10.2: Hash chaining for immutability
- Req 10.3: Tamper-evident audit trail
- Req 10.4: Include sensor data in audit logs
- Req 10.5: Append-only storage
- Req 10.6: Cryptographic integrity
- Req 10.7: Audit flags for security events

## Architecture

### Components

1. **DynamoDB Table** (`trustcapture-audit-logs`)
   - Partition key: `audit_id` (UUID)
   - Sort key: `timestamp` (ISO 8601)
   - Global Secondary Indexes:
     - `vendor_id-timestamp-index`: Query logs by vendor
     - `campaign_code-timestamp-index`: Query logs by campaign

2. **Audit Logger Service** (`app/services/audit_logger.py`)
   - Logs photo capture events
   - Implements hash chaining for immutability
   - Verifies chain integrity
   - Retrieves audit records

3. **Hash Chaining**
   - Each record contains SHA-256 hash of previous record
   - First record has `previous_record_hash = None`
   - Subsequent records link to previous via hash
   - Provides tamper-evident audit trail

## Setup

### 1. Install DynamoDB Local

For development, use DynamoDB Local:

```bash
# Download DynamoDB Local
wget https://s3.us-west-2.amazonaws.com/dynamodb-local/dynamodb_local_latest.tar.gz
tar -xzf dynamodb_local_latest.tar.gz

# Run DynamoDB Local
java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar -sharedDb -port 8000
```

Or use Docker:

```bash
docker run -p 8000:8000 amazon/dynamodb-local
```

### 2. Configure Environment Variables

Add to `.env`:

```bash
# DynamoDB Configuration
DYNAMODB_ENDPOINT_URL=http://localhost:8000  # For local development
DYNAMODB_REGION=us-east-1
DYNAMODB_TABLE_NAME=trustcapture-audit-logs

# For production (AWS DynamoDB)
# DYNAMODB_ENDPOINT_URL=  # Leave empty for AWS
# AWS_ACCESS_KEY_ID=your_access_key
# AWS_SECRET_ACCESS_KEY=your_secret_key
```

### 3. Create Audit Log Table

```bash
cd backend
python scripts/create_audit_table.py
```

This script is idempotent and can be run multiple times safely.

### 4. Verify Setup

```bash
# List tables
aws dynamodb list-tables --endpoint-url http://localhost:8000

# Describe table
aws dynamodb describe-table \
  --table-name trustcapture-audit-logs \
  --endpoint-url http://localhost:8000
```

## Audit Record Schema

```python
{
    'audit_id': str,              # UUID (partition key)
    'timestamp': str,             # ISO 8601 (sort key)
    'vendor_id': str,             # Vendor identifier
    'photo_id': str,              # Photo UUID
    'campaign_code': str,         # Campaign code
    'sensor_data': dict,          # GPS, WiFi, cell towers, etc.
    'signature': dict,            # Photo signature data
    'device_info': dict,          # Device model, OS, app version
    'previous_record_hash': str,  # SHA-256 hash of previous record
    'record_hash': str,           # SHA-256 hash of current record
    'audit_flags': list[str],     # Security/integrity flags
    'created_at': int             # Unix timestamp (for TTL)
}
```

## Audit Flags

The system supports the following audit flags:

- `ROOTED_DEVICE`: Device has root access
- `EMULATOR_MODE`: Running on emulator
- `LOW_GPS_ACCURACY`: GPS accuracy below threshold
- `SAFETYNET_FAILED`: SafetyNet attestation failed
- `OFFLINE_CAPTURE`: Photo captured offline
- `LOCATION_MISMATCH`: Location doesn't match expected profile

## Usage

### Logging Photo Capture Events

```python
from app.services.audit_logger import audit_logger, AuditFlag

# Log photo capture
audit_id = audit_logger.log_photo_capture(
    photo_id="550e8400-e29b-41d4-a716-446655440000",
    vendor_id="VND001",
    campaign_code="CAMP01",
    sensor_data={
        'gps_latitude': 37.7749295,
        'gps_longitude': -122.4194155,
        'gps_accuracy': 10.5,
        'wifi_networks': [...],
        'cell_towers': [...]
    },
    signature={
        'signature': 'base64_encoded_signature',
        'algorithm': 'SHA256withRSA',
        'timestamp': '2024-01-01T00:00:00Z'
    },
    device_info={
        'model': 'Pixel 6',
        'os_version': 'Android 13',
        'app_version': '1.0.0'
    },
    flags=[AuditFlag.LOW_GPS_ACCURACY]
)
```

### Retrieving Audit Records

```python
# Get specific audit record
record = audit_logger.get_audit_record(audit_id)

# Get vendor audit logs (newest first)
logs = audit_logger.get_vendor_audit_logs(
    vendor_id="VND001",
    limit=100
)
```

### Verifying Chain Integrity

```python
# Verify audit log chain for a vendor
is_valid, error = audit_logger.verify_chain_integrity("VND001")

if is_valid:
    print("Audit log chain is valid")
else:
    print(f"Chain integrity violation: {error}")
```

## Hash Chaining Algorithm

### Hash Calculation

The hash of each record is calculated using SHA-256 over the following fields:

```python
hash_data = {
    'audit_id': record['audit_id'],
    'timestamp': record['timestamp'],
    'vendor_id': record['vendor_id'],
    'photo_id': record['photo_id'],
    'campaign_code': record['campaign_code'],
    'sensor_data': record['sensor_data'],
    'signature': record['signature'],
    'previous_record_hash': record['previous_record_hash']
}

hash_string = json.dumps(hash_data, sort_keys=True, default=str)
record_hash = hashlib.sha256(hash_string.encode('utf-8')).hexdigest()
```

### Chain Verification

1. Retrieve all records for a vendor in chronological order
2. Verify first record has `previous_record_hash = None`
3. For each subsequent record:
   - Calculate hash of previous record
   - Compare with `previous_record_hash` in current record
   - If mismatch, chain is broken (tampering detected)

## Integration with Photo Upload

The audit logger is integrated into the photo upload API:

```python
from app.services.audit_logger import audit_logger, AuditFlag

@router.post("/photos/upload")
async def upload_photo(...):
    # ... photo upload logic ...
    
    # Determine audit flags
    flags = []
    if sensor_data.gps_accuracy > 50:
        flags.append(AuditFlag.LOW_GPS_ACCURACY)
    if device_info.get('rooted'):
        flags.append(AuditFlag.ROOTED_DEVICE)
    
    # Log to audit trail (non-blocking)
    try:
        audit_id = audit_logger.log_photo_capture(
            photo_id=str(photo.photo_id),
            vendor_id=vendor_id,
            campaign_code=campaign_code,
            sensor_data=sensor_data_dict,
            signature=signature_dict,
            device_info=device_info_dict,
            flags=flags
        )
    except Exception as e:
        # Log error but don't block upload
        logger.error(f"Audit logging failed: {e}")
    
    return PhotoUploadResponse(...)
```

## Error Handling

The audit logger is designed to fail gracefully:

1. **DynamoDB Unavailable**: Returns `None` instead of raising exception
2. **Network Errors**: Logs error and continues
3. **Invalid Data**: Validates input and logs warnings
4. **Chain Verification Failures**: Returns error message for investigation

**Important**: Audit logging failures should NOT block photo uploads. The system logs errors for later investigation.

## Testing

### Unit Tests

```bash
cd backend
python -m pytest tests/test_audit_logger.py -v
```

### Integration Tests with DynamoDB Local

```bash
# Start DynamoDB Local
docker run -d -p 8000:8000 amazon/dynamodb-local

# Run tests
python -m pytest tests/test_audit_logger.py -v

# Stop DynamoDB Local
docker stop $(docker ps -q --filter ancestor=amazon/dynamodb-local)
```

### Manual Testing

```python
# Create table
python scripts/create_audit_table.py

# Test logging
from app.services.audit_logger import audit_logger
import uuid

audit_id = audit_logger.log_photo_capture(
    photo_id=str(uuid.uuid4()),
    vendor_id="TEST01",
    campaign_code="TEST",
    sensor_data={'gps_latitude': 37.7749295},
    signature={'signature': 'test'},
    device_info={'model': 'Test Device'},
    flags=[]
)

print(f"Audit ID: {audit_id}")

# Verify chain
is_valid, error = audit_logger.verify_chain_integrity("TEST01")
print(f"Chain valid: {is_valid}")
```

## Production Deployment

### AWS DynamoDB

For production, use AWS DynamoDB:

1. **Create Table**:
   ```bash
   aws dynamodb create-table \
     --table-name trustcapture-audit-logs \
     --attribute-definitions \
       AttributeName=audit_id,AttributeType=S \
       AttributeName=timestamp,AttributeType=S \
       AttributeName=vendor_id,AttributeType=S \
       AttributeName=campaign_code,AttributeType=S \
     --key-schema \
       AttributeName=audit_id,KeyType=HASH \
       AttributeName=timestamp,KeyType=RANGE \
     --global-secondary-indexes \
       IndexName=vendor_id-timestamp-index,KeySchema=[{AttributeName=vendor_id,KeyType=HASH},{AttributeName=timestamp,KeyType=RANGE}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5} \
       IndexName=campaign_code-timestamp-index,KeySchema=[{AttributeName=campaign_code,KeyType=HASH},{AttributeName=timestamp,KeyType=RANGE}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5} \
     --provisioned-throughput \
       ReadCapacityUnits=5,WriteCapacityUnits=5
   ```

2. **Configure Environment**:
   ```bash
   DYNAMODB_ENDPOINT_URL=  # Empty for AWS
   DYNAMODB_REGION=us-east-1
   DYNAMODB_TABLE_NAME=trustcapture-audit-logs
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   ```

3. **Enable Auto Scaling** (recommended):
   - Configure auto-scaling for read/write capacity
   - Set target utilization to 70%
   - Min capacity: 5, Max capacity: 100

4. **Enable Point-in-Time Recovery**:
   ```bash
   aws dynamodb update-continuous-backups \
     --table-name trustcapture-audit-logs \
     --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true
   ```

5. **Configure TTL** (optional):
   ```bash
   aws dynamodb update-time-to-live \
     --table-name trustcapture-audit-logs \
     --time-to-live-specification "Enabled=true, AttributeName=created_at"
   ```

## Monitoring

### CloudWatch Metrics

Monitor the following metrics:

- `ConsumedReadCapacityUnits`
- `ConsumedWriteCapacityUnits`
- `UserErrors` (throttling)
- `SystemErrors`

### Alarms

Set up CloudWatch alarms for:

- High throttling rate
- Chain verification failures
- Audit logging errors

### Logging

All audit operations are logged with structured logging:

```python
logger.info(f"Logged audit record: audit_id={audit_id}, vendor_id={vendor_id}")
logger.error(f"Error logging audit record: {e}")
```

## Security Considerations

1. **Append-Only**: DynamoDB table should have append-only permissions
2. **Encryption**: Enable encryption at rest in DynamoDB
3. **Access Control**: Restrict access to audit logs via IAM policies
4. **Hash Chaining**: Provides tamper-evident trail
5. **Immutability**: Records cannot be modified after creation

## Troubleshooting

### DynamoDB Local Not Starting

```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill existing process
kill -9 $(lsof -t -i:8000)

# Restart DynamoDB Local
java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar -sharedDb -port 8000
```

### Table Creation Fails

```bash
# Check if table exists
aws dynamodb describe-table \
  --table-name trustcapture-audit-logs \
  --endpoint-url http://localhost:8000

# Delete and recreate
aws dynamodb delete-table \
  --table-name trustcapture-audit-logs \
  --endpoint-url http://localhost:8000

python scripts/create_audit_table.py
```

### Chain Verification Fails

```python
# Get detailed error
is_valid, error = audit_logger.verify_chain_integrity("VND001")
print(f"Error: {error}")

# Inspect records manually
logs = audit_logger.get_vendor_audit_logs("VND001", limit=10)
for log in logs:
    print(f"Audit ID: {log['audit_id']}")
    print(f"Previous Hash: {log.get('previous_record_hash')}")
    print(f"Record Hash: {log.get('record_hash')}")
    print()
```

## References

- [DynamoDB Local Documentation](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [Hash Chaining for Audit Logs](https://en.wikipedia.org/wiki/Hash_chain)
