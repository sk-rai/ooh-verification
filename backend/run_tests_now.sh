#!/bin/bash
# Quick test runner - checks database and runs tests

echo "=========================================="
echo "TrustCapture Test Runner"
echo "=========================================="
echo ""

# Check if test database exists
echo "1. Checking test database..."
DB_EXISTS=$(PGPASSWORD=dev_password_123 psql -U trustcapture -h localhost -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='trustcapture_test'" 2>/dev/null)

if [ "$DB_EXISTS" = "1" ]; then
    echo "✓ Test database exists"
else
    echo "⚠ Test database doesn't exist"
    echo ""
    echo "Creating test database manually..."
    echo "Please run this command:"
    echo ""
    echo "  sudo -u postgres psql -c \"CREATE DATABASE trustcapture_test OWNER trustcapture;\""
    echo ""
    read -p "Press Enter after creating the database..."
fi

# Check if migrations are applied
echo ""
echo "2. Checking migrations..."
TABLE_COUNT=$(PGPASSWORD=dev_password_123 psql -U trustcapture -h localhost -d trustcapture_test -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'" 2>/dev/null)

if [ "$TABLE_COUNT" -gt "0" ]; then
    echo "✓ Database has $TABLE_COUNT tables"
else
    echo "⚠ Database is empty, running migrations..."
    export DATABASE_URL="postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_test"
    python3 -m alembic upgrade head
    
    if [ $? -eq 0 ]; then
        echo "✓ Migrations applied"
    else
        echo "✗ Migration failed"
        exit 1
    fi
fi

# Run tests
echo ""
echo "3. Running tests..."
echo "=========================================="
pytest -v --tb=short

echo ""
echo "=========================================="
echo "Test run complete!"
echo "=========================================="
