# Audit Logging with PostgreSQL

## Overview

TrustCapture's audit logging system provides an **immutable, tamper-evident audit trail** for all photo capture events. The system uses **PostgreSQL** (not DynamoDB) to avoid cloud vendor lock-in.

## Key Features

✅ **No AWS Dependency** - Uses PostgreSQL instead of DynamoDB  
✅ **Append-Only Storage** - Enforced by database triggers  
✅ **Hash Chaining** - Cryptographic integrity verification  
✅ **Immutability** - Cannot update or delete audit records  
✅ **Comprehensive Data** - Captures sensor data, signatures, device info  
✅ **Audit Flags** - Track security events (rooted device, GPS issues, etc.)

## Architecture

### Database Table

```sql
CREATE TABLE audit_logs (
    audit_id UUID PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    vendor_id VARCHAR(6) NOT NULL,
    photo_id UUID NOT NULL,
    campaign_code VARCHAR(50) NOT NULL,
    sensor_data JSONB NOT NULL,
    signature JSONB NOT NULL,
    device_info JSONB NOT NULL,
    previous_record_hash VARCHAR(64),  -- SHA-256 hash
    record_hash VARCHAR(64) NOT NULL,
    audit_flags TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Immutability Enforcement

PostgreSQL triggers prevent any modifications:

```sql
CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit logs are immutable and cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_immutable_update
    BEFORE UPDATE ON audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_log_modification();

CREATE TRIGGER audit_log_immutable_delete
    BEFORE DELETE ON audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_log_modification();
```

### Hash Chaining

Each audit record contains:
- `record_hash`: SHA-256 hash of current record
- `previous_record_hash`: Hash of previous record (NULL for first record)

This creates a blockchain-like chain that detects tampering.

## Usage

### Logging a Photo Capture

```python
from app.services.audit_logger import AuditLogger, AuditFlag
from app.core.database import get_db

async def log_capture(db: AsyncSession):
    audit_logger = AuditLogger(db)
    
    audit_id = await audit_logger.log_photo_capture(
        photo_id=str(photo.photo_id),
        vendor_id=vendor.vendor_id,
        campaign_code=campaign.campaign_code,
        sensor_data={
            'gps_latitude': 37.7749,
            'gps_longitude': -122.4194,
            'gps_accuracy': 10.5,
            'wifi_networks': [...],
            'cell_towers': [...]
        },
        signature={
            'signature': 'base64_encoded_signature',
            'algorithm': 'SHA256withRSA',
            'timestamp': '2024-03-05T10:00:00Z'
        },
        device_info={
            'model': 'Pixel 6',
            'os_version': 'Android 13',
            'app_version': '1.0.0'
        },
        flags=[AuditFlag.LOW_GPS_ACCURACY.value]
    )
```

### Verifying Chain Integrity

```python
is_valid, error = await audit_logger.verify_chain_integrity('VND001')

if is_valid:
    print("✅ Audit chain is intact")
else:
    print(f"❌ Chain broken: {error}")
```

### Retrieving Audit Logs

```python
# Get specific record
record = await audit_logger.get_audit_record(audit_id)

# Get vendor's audit logs
logs = await audit_logger.get_vendor_audit_logs('VND001', limit=100)
```

## Audit Flags

The system tracks security and integrity events:

```python
class AuditFlag(str, Enum):
    ROOTED_DEVICE = "ROOTED_DEVICE"
    EMULATOR_MODE = "EMULATOR_MODE"
    LOW_GPS_ACCURACY = "LOW_GPS_ACCURACY"
    SAFETYNET_FAILED = "SAFETYNET_FAILED"
    OFFLINE_CAPTURE = "OFFLINE_CAPTURE"
    LOCATION_MISMATCH = "LOCATION_MISMATCH"
```

## Migration from DynamoDB

This system was refactored from DynamoDB to PostgreSQL to:

1. **Eliminate AWS dependency** - No vendor lock-in
2. **Simplify infrastructure** - Use existing PostgreSQL database
3. **Reduce costs** - No separate DynamoDB service
4. **Maintain functionality** - Same hash chaining and immutability

### What Changed

- ✅ Storage backend: DynamoDB → PostgreSQL
- ✅ Immutability: IAM policies → Database triggers
- ✅ API: Synchronous → Async (SQLAlchemy)
- ✅ Dependencies: boto3 → asyncpg

### What Stayed the Same

- ✅ Hash chaining algorithm (SHA-256)
- ✅ AuditFlag enum
- ✅ Data structure
- ✅ API interface (log_photo_capture, verify_chain_integrity, etc.)

## Database Setup

### Run Migration

```bash
cd backend
alembic upgrade head
```

This creates:
- `audit_logs` table
- Indexes for efficient querying
- Immutability triggers

### Verify Setup

```bash
python3 test_audit_postgres.py
```

## Performance

### Indexes

Efficient querying with composite indexes:

```sql
CREATE INDEX idx_audit_logs_vendor_timestamp 
    ON audit_logs(vendor_id, timestamp DESC);

CREATE INDEX idx_audit_logs_campaign_timestamp 
    ON audit_logs(campaign_code, timestamp DESC);
```

### Query Performance

- Single record retrieval: O(1) via primary key
- Vendor logs: O(log n) via indexed query
- Chain verification: O(n) for n records

## Security Considerations

1. **Immutability**: Database triggers prevent modifications
2. **Hash Chaining**: Detects tampering attempts
3. **Comprehensive Logging**: All capture events recorded
4. **Audit Flags**: Track security anomalies
5. **Timestamp Integrity**: ISO 8601 format with timezone

## Testing

Run audit logger tests:

```bash
pytest tests/test_audit_logger.py -v
```

Tests cover:
- ✅ Record creation
- ✅ Hash chaining
- ✅ Chain integrity verification
- ✅ Immutability enforcement
- ✅ Audit flags
- ✅ Record retrieval

## Requirements Traceability

- **Req 10.1**: Log all photo capture events ✅
- **Req 10.2**: Hash chaining for immutability ✅
- **Req 10.3**: Tamper-evident audit trail ✅
- **Req 10.4**: Include sensor data in audit logs ✅
- **Req 10.5**: Append-only storage ✅
- **Req 10.6**: Cryptographic integrity ✅
- **Req 10.7**: Audit flags for security events ✅

## Benefits Over DynamoDB

| Feature | DynamoDB | PostgreSQL |
|---------|----------|------------|
| Vendor Lock-in | ❌ AWS only | ✅ Open source |
| Infrastructure | Separate service | ✅ Existing DB |
| Cost | Pay per request | ✅ Included |
| Immutability | IAM policies | ✅ DB triggers |
| Querying | Limited | ✅ Full SQL |
| Transactions | Limited | ✅ ACID |
| Backup | Separate | ✅ Unified |

## Conclusion

The PostgreSQL-based audit logging system provides the same security guarantees as DynamoDB while eliminating cloud vendor lock-in and simplifying infrastructure management.
