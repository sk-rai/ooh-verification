# Manual Database Setup - Step by Step

Follow these steps to fix the main database and run migrations.

## Step 1: Reset Database Password

Open a terminal and run:

```bash
sudo -u postgres psql
```

Then in the PostgreSQL prompt, run these commands:

```sql
-- Reset password
ALTER USER trustcapture WITH PASSWORD 'dev_password_123';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE trustcapture_db TO trustcapture;

-- Verify (should show trustcapture user)
\du trustcapture

-- Exit
\q
```

**Expected output:** You should see "ALTER ROLE" confirming the password was changed.

---

## Step 2: Update .env File

```bash
cd /home/lynksavvy/projects/trustcapture/backend

# Create .env file
cat > .env << 'EOF'
DATABASE_URL=postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DEBUG=True
SECRET_KEY=dev-secret-key-change-in-production
JWT_SECRET_KEY=dev-jwt-secret-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080
STORAGE_TYPE=mock
EOF

echo "✓ .env file created"
```

---

## Step 3: Test Database Connection

```bash
cd /home/lynksavvy/projects/trustcapture/backend
python3 test_db_connection.py
```

**Expected output:** Should show "✅ SUCCESS! Connected to PostgreSQL"

---

## Step 4: Check Current Migration Status

```bash
cd /home/lynksavvy/projects/trustcapture/backend
python3 -m alembic current
```

**Expected output:** Should show `002_audit_logs` (current version)

---

## Step 5: Run Database Migrations

```bash
cd /home/lynksavvy/projects/trustcapture/backend
python3 -m alembic upgrade head
```

**Expected output:** 
```
INFO  [alembic.runtime.migration] Running upgrade 002_audit_logs -> 003_subscription_enhancements
```

---

## Step 6: Verify Database Status

```bash
cd /home/lynksavvy/projects/trustcapture/backend
python3 check_db_status.py
```

**Expected output:** Should show all tables including `subscriptions` with new columns

---

## Step 7: Verify Migration Applied

```bash
cd /home/lynksavvy/projects/trustcapture/backend
python3 -m alembic current
```

**Expected output:** Should show `003_subscription_enhancements` (new version)

---

## Troubleshooting

### If Step 1 fails with "role does not exist"

The user doesn't exist. Create it:

```sql
-- In psql prompt
CREATE USER trustcapture WITH PASSWORD 'dev_password_123';
CREATE DATABASE trustcapture_db OWNER trustcapture;
GRANT ALL PRIVILEGES ON DATABASE trustcapture_db TO trustcapture;
\q
```

### If Step 3 fails with "password authentication failed"

Double-check the password was set correctly:

```bash
sudo -u postgres psql
ALTER USER trustcapture WITH PASSWORD 'dev_password_123';
\q
```

### If Step 5 fails with "relation does not exist"

The initial tables weren't created. Run from the beginning:

```bash
python3 -m alembic downgrade base
python3 -m alembic upgrade head
```

---

## Quick Copy-Paste Commands

If you want to run all steps quickly, copy and paste this entire block:

```bash
# Step 1: Reset password (requires sudo)
sudo -u postgres psql -c "ALTER USER trustcapture WITH PASSWORD 'dev_password_123';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE trustcapture_db TO trustcapture;"

# Step 2: Create .env
cd /home/lynksavvy/projects/trustcapture/backend
cat > .env << 'EOF'
DATABASE_URL=postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_db
DEBUG=True
SECRET_KEY=dev-secret-key
JWT_SECRET_KEY=dev-jwt-secret
JWT_ALGORITHM=HS256
STORAGE_TYPE=mock
EOF

# Step 3: Test connection
python3 test_db_connection.py

# Step 4: Check current migration
python3 -m alembic current

# Step 5: Run migrations
python3 -m alembic upgrade head

# Step 6: Verify
python3 check_db_status.py
python3 -m alembic current
```

---

## Success Indicators

After completing all steps, you should see:

✅ Database connection successful  
✅ Migration at `003_subscription_enhancements`  
✅ Tables include: clients, subscriptions, vendors, campaigns, photos, audit_logs, etc.  
✅ Subscriptions table has new columns: payment_gateway, gateway_subscription_id, vendors_quota, etc.

---

## Next: Testing the Implementation

Once the database is set up, proceed to test the quota enforcement:

```bash
# Start the server
cd /home/lynksavvy/projects/trustcapture/backend
uvicorn app.main:app --reload

# In another terminal, test the API
curl http://localhost:8000/api/subscriptions/tiers
curl http://localhost:8000/api/subscriptions/health
```
