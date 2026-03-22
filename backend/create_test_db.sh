#!/bin/bash
# Create test database for TrustCapture testing

echo "Creating test database..."

# Create database
PGPASSWORD=dev_password_123 psql -U trustcapture -h localhost -d postgres -c "DROP DATABASE IF EXISTS trustcapture_test;" 2>/dev/null
PGPASSWORD=dev_password_123 psql -U trustcapture -h localhost -d postgres -c "CREATE DATABASE trustcapture_test;"

if [ $? -eq 0 ]; then
    echo "✓ Test database created successfully"
    
    # Run migrations
    echo "Running migrations on test database..."
    export DATABASE_URL="postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_test"
    python3 -m alembic upgrade head
    
    if [ $? -eq 0 ]; then
        echo "✓ Migrations applied successfully"
        echo ""
        echo "Test database ready at: trustcapture_test"
        echo "Connection string: postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_test"
    else
        echo "✗ Migration failed"
        exit 1
    fi
else
    echo "✗ Database creation failed"
    exit 1
fi
