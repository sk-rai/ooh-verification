#!/bin/bash
# Check if test database exists and create if needed

echo "Checking test database..."

# Check if database exists
DB_EXISTS=$(PGPASSWORD=dev_password_123 psql -U trustcapture -h localhost -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='trustcapture_test'")

if [ "$DB_EXISTS" = "1" ]; then
    echo "✓ Test database already exists"
else
    echo "Creating test database..."
    # Try to create database
    PGPASSWORD=dev_password_123 psql -U trustcapture -h localhost -d postgres -c "CREATE DATABASE trustcapture_test;" 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✓ Test database created successfully"
    else
        echo "⚠ Could not create database, trying alternative method..."
        # Try with postgres user if trustcapture user doesn't have permission
        sudo -u postgres psql -c "CREATE DATABASE trustcapture_test OWNER trustcapture;" 2>&1
        
        if [ $? -eq 0 ]; then
            echo "✓ Test database created with postgres user"
        else
            echo "✗ Database creation failed"
            echo ""
            echo "Manual creation required. Run:"
            echo "  sudo -u postgres psql -c \"CREATE DATABASE trustcapture_test OWNER trustcapture;\""
            exit 1
        fi
    fi
fi

# Run migrations
echo ""
echo "Running migrations on test database..."
export DATABASE_URL="postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_test"
python3 -m alembic upgrade head 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Migrations applied successfully"
    echo ""
    echo "Test database ready!"
    echo "Connection: postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_test"
else
    echo "✗ Migration failed"
    exit 1
fi
