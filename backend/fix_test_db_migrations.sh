#!/bin/bash
# Fix test database migration state

set -e

echo "Connecting to test database and resetting alembic version..."
sudo -u postgres psql -d trustcapture_test -c "DELETE FROM alembic_version;"

echo "Dropping all tables to start fresh..."
sudo -u postgres psql -d trustcapture_test -c "
DROP TABLE IF EXISTS campaign_locations CASCADE;
DROP TABLE IF EXISTS campaign_vendor_assignments CASCADE;
DROP TABLE IF EXISTS photos CASCADE;
DROP TABLE IF EXISTS photo_signatures CASCADE;
DROP TABLE IF EXISTS sensor_data CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS subscriptions CASCADE;
DROP TABLE IF EXISTS campaigns CASCADE;
DROP TABLE IF EXISTS vendors CASCADE;
DROP TABLE IF EXISTS clients CASCADE;
DROP TABLE IF EXISTS location_profiles CASCADE;
DROP TABLE IF EXISTS tenant_config CASCADE;
"

echo "Running migrations from scratch..."
cd ~/projects/trustcapture/backend
export TEST_DATABASE_URL='postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_test'
alembic upgrade head

echo "✓ Test database migrations fixed!"
