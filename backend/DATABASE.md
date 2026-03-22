# TrustCapture Database Documentation

## Overview

TrustCapture uses PostgreSQL as the primary database with the following architecture:
- **PostgreSQL 15+**: Primary relational database for all application data
- **DynamoDB**: Immutable audit logs (configured separately)
- **Redis**: Session cache and rate limiting (configured separately)

## Database Schema

### Core Tables

#### 1. **clients** - Client Accounts
Stores company/organization accounts that manage vendors and campaigns.

**Key Columns:**
- `client_id` (UUID, PK)
- `email` (unique, indexed)
- `subscription_tier` (free/pro/enterprise)
- `stripe_customer_id` (Stripe integration)

#### 2. **vendors** - Field Workers
Stores vendor accounts created by clients who capture photos via Android app.

**Key Columns:**
- `vendor_id` (6-char alphanumeric, PK) - e.g., "A3X9K2"
- `created_by_client_id` (FK → clients)
- `device_id` (Android device ID)
- `public_key` (RSA/ECDSA public key from Android Keystore)

#### 3. **campaigns** - Verification Campaigns
Defines what photos to capture and where.

**Key Columns:**
- `campaign_id` (UUID, PK)
- `campaign_code` (unique, indexed) - e.g., "RURAL-MP-2026"
- `campaign_type` (ooh/construction/insurance/delivery/healthcare/property_management)
- `client_id` (FK → clients)

#### 4. **location_profiles** - Expected Location Data
Defines expected sensor patterns for location verification.

**Key Columns:**
- `expected_latitude/longitude` (7 decimal precision = ~1.1cm accuracy)
- `tolerance_meters` (acceptable distance variance)
- `expected_wifi_bssids` (array of WiFi MAC addresses)
- `expected_cell_tower_ids` (array of cell tower IDs)
- `expected_pressure_min/max` (barometric pressure range)

#### 5. **campaign_vendor_assignments** - Many-to-Many Junction
Links vendors to campaigns they can capture photos for.

#### 6. **photos** - Captured Photos Metadata
Stores photo metadata and verification status.

**Key Columns:**
- `photo_id` (UUID, PK)
- `s3_key` (S3 object path)
- `verification_status` (pending/verified/flagged/rejected)
- `signature_valid` (cryptographic signature check result)
- `location_match_score` (0-100 confidence)
- `distance_from_expected` (meters)

#### 7. **sensor_data** - Multi-Sensor Verification Data
Stores comprehensive sensor readings for each photo.

**Key Columns:**
- GPS: latitude, longitude, altitude, accuracy, provider, satellite_count
- WiFi: networks (JSONB array)
- Cell Towers: towers (JSONB array)
- Environmental: barometer_pressure, ambient_light_lux, magnetic_field_*
- Hand Tremor: frequency, is_human, confidence
- Metadata: location_hash, confidence_score, schema_version

#### 8. **photo_signatures** - Cryptographic Signatures
Stores cryptographic signatures for tamper detection.

**Key Columns:**
- `signature_data` (Base64 encoded signature)
- `algorithm` (SHA256withRSA or SHA256withECDSA)
- `location_hash` (SHA-256 hash of sensor data)

#### 9. **subscriptions** - Subscription Management
Tracks client subscription details and usage.

**Key Columns:**
- `tier` (free/pro/enterprise)
- `photos_quota` (monthly limit)
- `photos_used` (current usage)
- `stripe_subscription_id` (Stripe integration)

## Setup Instructions

### 1. Install PostgreSQL

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS:**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Windows:**
Download and install from https://www.postgresql.org/download/windows/

### 2. Create Database and User

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE trustcapture_db;
CREATE USER trustcapture WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE trustcapture_db TO trustcapture;

# Exit psql
\q
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and update:

```bash
cp .env.example .env
```

Edit `.env`:
```
DATABASE_URL=postgresql+asyncpg://trustcapture:your_secure_password@localhost:5432/trustcapture_db
```

### 4. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 5. Run Database Migrations

```bash
# Run migrations
alembic upgrade head

# Check current version
alembic current

# View migration history
alembic history
```

## Database Operations

### Create a New Migration

After modifying models:

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "description of changes"

# Review the generated migration file in alembic/versions/
# Edit if necessary, then apply:
alembic upgrade head
```

### Rollback Migrations

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Rollback all migrations
alembic downgrade base
```

### Reset Database (Development Only)

```bash
# Drop all tables
alembic downgrade base

# Recreate all tables
alembic upgrade head
```

## Indexes

The following indexes are created for performance:

**clients:**
- `idx_clients_email` on email
- `idx_clients_subscription` on (subscription_tier, subscription_status)

**vendors:**
- `idx_vendors_client` on created_by_client_id
- `idx_vendors_phone` on phone_number
- `idx_vendors_status` on status

**campaigns:**
- `idx_campaigns_client` on client_id
- `idx_campaigns_code` on campaign_code
- `idx_campaigns_dates` on (start_date, end_date)

**photos:**
- `idx_photos_campaign` on campaign_id
- `idx_photos_vendor` on vendor_id
- `idx_photos_timestamp` on capture_timestamp
- `idx_photos_status` on verification_status

**sensor_data:**
- `idx_sensor_data_photo` on photo_id
- `idx_sensor_data_gps` on (gps_latitude, gps_longitude)

## Data Types

### Enums

- **SubscriptionTier**: free, pro, enterprise
- **SubscriptionStatus**: active, cancelled, expired, past_due
- **VendorStatus**: active, inactive
- **CampaignType**: ooh, construction, insurance, delivery, healthcare, property_management
- **CampaignStatus**: active, completed, cancelled
- **VerificationStatus**: pending, verified, flagged, rejected

### JSONB Columns

**sensor_data.wifi_networks** format:
```json
[
  {
    "ssid": "Network1",
    "bssid": "00:11:22:33:44:55",
    "signal_strength": -45,
    "frequency": 2437
  }
]
```

**sensor_data.cell_towers** format:
```json
[
  {
    "cell_id": 12345,
    "lac": 100,
    "mcc": 404,
    "mnc": 45,
    "signal_strength": -75,
    "network_type": "LTE"
  }
]
```

## Backup and Restore

### Backup

```bash
# Full database backup
pg_dump -U trustcapture -h localhost trustcapture_db > backup_$(date +%Y%m%d).sql

# Compressed backup
pg_dump -U trustcapture -h localhost trustcapture_db | gzip > backup_$(date +%Y%m%d).sql.gz
```

### Restore

```bash
# Restore from backup
psql -U trustcapture -h localhost trustcapture_db < backup_20260304.sql

# Restore from compressed backup
gunzip -c backup_20260304.sql.gz | psql -U trustcapture -h localhost trustcapture_db
```

## Performance Tuning

### Recommended PostgreSQL Settings

Edit `postgresql.conf`:

```ini
# Memory
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 16MB

# Connections
max_connections = 100

# Query Planning
random_page_cost = 1.1  # For SSD storage
effective_io_concurrency = 200

# Write Ahead Log
wal_buffers = 16MB
checkpoint_completion_target = 0.9
```

### Analyze Tables

```sql
-- Analyze all tables
ANALYZE;

-- Analyze specific table
ANALYZE photos;

-- Vacuum and analyze
VACUUM ANALYZE;
```

## Monitoring

### Check Database Size

```sql
SELECT pg_size_pretty(pg_database_size('trustcapture_db'));
```

### Check Table Sizes

```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Check Active Connections

```sql
SELECT count(*) FROM pg_stat_activity WHERE datname = 'trustcapture_db';
```

### Check Slow Queries

```sql
SELECT
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

## Troubleshooting

### Connection Issues

```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

### Permission Issues

```sql
-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE trustcapture_db TO trustcapture;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO trustcapture;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO trustcapture;
```

### Reset Alembic

If migrations are out of sync:

```bash
# Delete alembic_version table
psql -U trustcapture -d trustcapture_db -c "DROP TABLE IF EXISTS alembic_version;"

# Stamp current version
alembic stamp head
```

## Security Best Practices

1. **Use strong passwords** for database users
2. **Enable SSL/TLS** for database connections in production
3. **Restrict network access** using `pg_hba.conf`
4. **Regular backups** with encryption
5. **Monitor access logs** for suspicious activity
6. **Use connection pooling** to prevent connection exhaustion
7. **Encrypt sensitive data** at rest and in transit

## Next Steps

After setting up the database:

1. ✅ Database schema created
2. ⏭️ Implement authentication API (Task 3)
3. ⏭️ Implement client management API (Task 4)
4. ⏭️ Implement vendor management API (Task 6)
5. ⏭️ Implement campaign management API (Task 7)
