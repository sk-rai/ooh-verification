#!/bin/bash
# Setup Main Database for TrustCapture
# This script will fix the database password and run migrations

set -e  # Exit on error

echo "========================================================================"
echo "TrustCapture Database Setup - Main Database"
echo "========================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Check if PostgreSQL is running
echo "📊 Step 1: Checking PostgreSQL status..."
if sudo systemctl is-active --quiet postgresql; then
    echo -e "${GREEN}✓ PostgreSQL is running${NC}"
else
    echo -e "${RED}✗ PostgreSQL is not running${NC}"
    echo "Starting PostgreSQL..."
    sudo systemctl start postgresql
    sleep 2
fi
echo ""

# Step 2: Reset password
echo "🔐 Step 2: Resetting database password..."
echo "   User: trustcapture"
echo "   Password: dev_password_123"
echo "   Database: trustcapture_db"
echo ""

sudo -u postgres psql << 'EOF'
-- Reset password
ALTER USER trustcapture WITH PASSWORD 'dev_password_123';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE trustcapture_db TO trustcapture;

-- Show confirmation
\echo 'Password reset successful!'
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Password reset complete${NC}"
else
    echo -e "${RED}✗ Password reset failed${NC}"
    echo "Trying to create user and database..."
    
    sudo -u postgres psql << 'EOF'
-- Create database if not exists
SELECT 'CREATE DATABASE trustcapture_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'trustcapture_db')\gexec

-- Create user if not exists
DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'trustcapture') THEN
      CREATE USER trustcapture WITH PASSWORD 'dev_password_123';
   END IF;
END
$$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE trustcapture_db TO trustcapture;

\echo 'Database and user created!'
EOF
fi
echo ""

# Step 3: Update .env file
echo "📝 Step 3: Updating .env file..."
cd /home/lynksavvy/projects/trustcapture/backend

# Backup existing .env if it exists
if [ -f .env ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo "   Backed up existing .env"
fi

# Create new .env with correct DATABASE_URL
cat > .env << 'ENVEOF'
# Database Configuration
DATABASE_URL=postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Application
APP_NAME=TrustCapture
DEBUG=True
SECRET_KEY=dev-secret-key-change-in-production

# JWT
JWT_SECRET_KEY=dev-jwt-secret-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080

# Storage (for testing without S3)
STORAGE_TYPE=mock

# Add other settings from .env.example as needed
ENVEOF

echo -e "${GREEN}✓ .env file created${NC}"
echo ""

# Step 4: Test connection
echo "🔍 Step 4: Testing database connection..."
python3 test_db_connection.py
echo ""

# Step 5: Check current migration status
echo "📋 Step 5: Checking migration status..."
python3 -m alembic current
echo ""

# Step 6: Run migrations
echo "🚀 Step 6: Running database migrations..."
echo "   This will apply migration: 003_subscription_enhancements"
echo ""

python3 -m alembic upgrade head

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ Migrations applied successfully!${NC}"
else
    echo ""
    echo -e "${RED}✗ Migration failed${NC}"
    echo "Check the error above for details"
    exit 1
fi
echo ""

# Step 7: Verify database status
echo "✅ Step 7: Verifying database status..."
python3 check_db_status.py
echo ""

echo "========================================================================"
echo -e "${GREEN}DATABASE SETUP COMPLETE!${NC}"
echo "========================================================================"
echo ""
echo "📊 Summary:"
echo "   Database: trustcapture_db"
echo "   User: trustcapture"
echo "   Password: dev_password_123"
echo "   Migration: 003_subscription_enhancements"
echo ""
echo "🎯 Next Steps:"
echo "   1. Start the server: uvicorn app.main:app --reload"
echo "   2. Test quota enforcement"
echo "   3. Check usage stats: GET /api/subscriptions/usage"
echo ""
echo "📝 Database URL in .env:"
echo "   DATABASE_URL=postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_db"
echo ""
echo "========================================================================"
