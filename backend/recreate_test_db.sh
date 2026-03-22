#!/bin/bash
# Script to recreate test database from scratch

set -e

echo "Dropping test database..."
sudo -u postgres psql -c "DROP DATABASE IF EXISTS trustcapture_test;"

echo "Creating test database..."
sudo -u postgres psql -c "CREATE DATABASE trustcapture_test OWNER trustcapture;"

echo "Running migrations on test database..."
cd ~/projects/trustcapture/backend
export TEST_DATABASE_URL='postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_test'
alembic upgrade head

echo "✓ Test database recreated successfully!"
