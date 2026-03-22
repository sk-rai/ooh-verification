#!/bin/bash
echo "=========================================="
echo "Setting up Test Database"
echo "=========================================="

# Step 1: Create test database
echo ""
echo "Step 1: Creating test database..."
PGPASSWORD=dev_password_123 psql -U trustcapture -h localhost -d postgres -c "DROP DATABASE IF EXISTS trustcapture_test;" 2>/dev/null || true
PGPASSWORD=dev_password_123 psql -U trustcapture -h localhost -d postgres -c "CREATE DATABASE trustcapture_test OWNER trustcapture;"

if [ $? -eq 0 ]; then
    echo "✓ Test database created"
else
    echo "✗ Failed to create test database"
    echo "Trying with sudo..."
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS trustcapture_test;" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE trustcapture_test OWNER trustcapture;"
fi

# Step 2: Run migrations on test database
echo ""
echo "Step 2: Running migrations on test database..."
cd ~/projects/trustcapture/backend
export DATABASE_URL="postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_test"
python3 -m alembic upgrade head

if [ $? -eq 0 ]; then
    echo "✓ Migrations applied successfully"
else
    echo "✗ Migration failed"
    exit 1
fi

# Step 3: Verify tenant_id column exists
echo ""
echo "Step 3: Verifying audit_logs table structure..."
PGPASSWORD=dev_password_123 psql -U trustcapture -h localhost -d trustcapture_test -c "\d audit_logs" | grep tenant_id

if [ $? -eq 0 ]; then
    echo "✓ tenant_id column exists in audit_logs"
else
    echo "✗ tenant_id column missing in audit_logs"
fi

echo ""
echo "=========================================="
echo "Test Database Setup Complete!"
echo "=========================================="
echo ""
echo "Now run: python3 -m pytest tests/ -v"
