# Database Setup Guide - TrustCapture

## Current Situation

**Problem:** The main database (`trustcapture_db`) has authentication issues.  
**Working:** Test database (`test_trustcapture`) is accessible but incomplete.

## Option 1: Fix Main Database Password (RECOMMENDED)

This will fix the main production database.

### Step 1: Reset Password
```bash
# Connect to PostgreSQL as postgres user
sudo -u postgres psql

# Reset the password
ALTER USER trustcapture WITH PASSWORD 'dev_password_123';

# Verify the user exists
\du trustcapture

# Exit
\q
```

### Step 2: Update .env File
```bash
cd /home/lynksavvy/projects/trustcapture/backend

# Create or update .env file
cat > .env << 'EOF'
# Database
DATABASE_URL=postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_db

# Other settings (copy from .env.example if needed)
DEBUG=True
SECRET_KEY=your-secret-key-here
EOF
```

### Step 3: Test Connection
```bash
python3 test_db_connection.py
```

### Step 4: Run Migrations
```bash
# Check current status
python3 -m alembic current

# Apply all migrations
python3 -m alembic upgrade head
```

## Option 2: Use Test Database (QUICK FIX)

Use the test database for development/testing.

### Step 1: Update .env
```bash
cd /home/lynksavvy/projects/trustcapture/backend

cat > .env << 'EOF'
# Database (using test database)
DATABASE_URL=postgresql+asyncpg://test:test@localhost:5432/test_trustcapture

# Other settings
DEBUG=True
SECRET_KEY=your-secret-key-here
EOF
```

### Step 2: Reset Test Database
```bash
# Drop and recreate all tables
python3 -m alembic downgrade base
python3 -m alembic upgrade head
```

## Option 3: Create Fresh Database

Start completely fresh with a new database.

### Step 1: Create New Database
```bash
sudo -u postgres psql

CREATE DATABASE trustcapture_dev;
CREATE USER trustcapture_dev WITH PASSWORD 'dev123';
GRANT ALL PRIVILEGES ON DATABASE trustcapture_dev TO trustcapture_dev;
\q
```

### Step 2: Update .env
```bash
cd /home/lynksavvy/projects/trustcapture/backend

cat > .env << 'EOF'
DATABASE_URL=postgresql+asyncpg://trustcapture_dev:dev123@localhost:5432/trustcapture_dev
DEBUG=True
SECRET_KEY=your-secret-key-here
EOF
```

### Step 3: Run Migrations
```bash
python3 -m alembic upgrade head
```

## Verification Steps

After fixing the database, verify everything works:

### 1. Check Connection
```bash
python3 test_db_connection.py
```

### 2. Check Database Status
```bash
python3 check_db_status.py
```

### 3. Check Migration Status
```bash
python3 -m alembic current
# Should show: 003_subscription_enhancements
```

### 4. Verify Tables
```bash
python3 check_db_status.py
# Should show all tables including subscriptions
```

## Expected Tables After Migration

After running all migrations, you should have these tables:

1. `alembic_version` - Migration tracking
2. `clients` - Client accounts
3. `subscriptions` - Subscription details (NEW in 003)
4. `vendors` - Field workers
5. `campaigns` - Photo campaigns
6. `location_profiles` - Expected locations
7. `campaign_vendor_assignments` - Campaign-vendor links
8. `photos` - Uploaded photos
9. `sensor_data` - GPS and sensor data
10. `photo_signatures` - Cryptographic signatures
11. `audit_logs` - Immutable audit trail (NEW in 002)

## Troubleshooting

### "password authentication failed"
- Password is wrong
- User doesn't exist
- Solution: Use Option 1 to reset password

### "database does not exist"
- Database wasn't created
- Solution: Use Option 3 to create fresh database

### "relation does not exist"
- Migrations not applied
- Solution: Run `python3 -m alembic upgrade head`

### "alembic_version not found"
- Database never initialized
- Solution: Run `python3 -m alembic upgrade head`

## Quick Commands Reference

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# List databases
sudo -u postgres psql -l

# Connect to database
sudo -u postgres psql -d trustcapture_db

# Check current migration
python3 -m alembic current

# Apply migrations
python3 -m alembic upgrade head

# Rollback one migration
python3 -m alembic downgrade -1

# Reset to beginning
python3 -m alembic downgrade base
```

## Recommended Action

**For immediate testing:** Use Option 2 (test database)  
**For production setup:** Use Option 1 (fix main database)

Choose the option that works best for your situation!
