#!/bin/bash
# Simple test database setup

set -e

echo "Running migrations on test database..."
cd ~/projects/trustcapture/backend
export TEST_DATABASE_URL='postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_test'
alembic upgrade head

echo "✓ Test database setup complete!"
