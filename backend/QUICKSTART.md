# TrustCapture Backend - Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- pip or poetry

### Step 1: Install PostgreSQL

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**macOS:**
```bash
brew install postgresql@15
brew services start postgresql@15
```

### Step 2: Create Database

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Run these commands:
CREATE DATABASE trustcapture_db;
CREATE USER trustcapture WITH PASSWORD 'dev_password_123';
GRANT ALL PRIVILEGES ON DATABASE trustcapture_db TO trustcapture;
\q
```

### Step 3: Set Up Python Environment

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and update DATABASE_URL:
# DATABASE_URL=postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_db
```

### Step 5: Run Database Migrations

```bash
# Run migrations to create all tables
alembic upgrade head

# Verify migration
alembic current
```

### Step 6: Seed Sample Data (Optional)

```bash
# Add sample data for testing
python scripts/db_setup.py seed
```

You should see:
```
✅ Sample data created successfully!

📋 Sample Data:
   Client: demo@trustcapture.com (password: password123)
   Vendor 1: ABC123 - John Doe
   Vendor 2: XYZ789 - Jane Smith
   Campaign: DEMO-2026-001 - Demo Campaign
   Location: 12.9715987, 77.5945627
```

### Step 7: Verify Setup

```bash
# Check database connection and stats
python scripts/db_setup.py check
```

Expected output:
```
✅ Database connection successful!
📊 PostgreSQL version: PostgreSQL 15.x ...

📊 Database Statistics:
   Clients: 1
   Vendors: 2
   Campaigns: 1
   Location Profiles: 1
   Campaign Assignments: 2
   Subscriptions: 1
```

## ✅ You're Ready!

Your database is now set up with:
- ✅ 9 tables created
- ✅ 20 indexes for performance
- ✅ 6 enum types for type safety
- ✅ Sample data for testing

## 🎯 Next Steps

### Option 1: Start Building APIs

Continue with Task 3 - Implement Authentication:
```bash
# Create authentication endpoints
# See tasks.md for details
```

### Option 2: Explore the Database

```bash
# Connect to database
psql -U trustcapture -d trustcapture_db

# List tables
\dt

# View clients
SELECT * FROM clients;

# View vendors
SELECT * FROM vendors;

# View campaigns
SELECT * FROM campaigns;
```

### Option 3: Test Database Operations

Create a test file `test_db.py`:

```python
import asyncio
from app.core.database import AsyncSessionLocal
from app.models import Client, Vendor, Campaign
from sqlalchemy import select

async def test_queries():
    async with AsyncSessionLocal() as session:
        # Get all clients
        result = await session.execute(select(Client))
        clients = result.scalars().all()
        print(f"Found {len(clients)} clients")
        
        # Get all vendors
        result = await session.execute(select(Vendor))
        vendors = result.scalars().all()
        print(f"Found {len(vendors)} vendors")
        
        # Get all campaigns
        result = await session.execute(select(Campaign))
        campaigns = result.scalars().all()
        print(f"Found {len(campaigns)} campaigns")

if __name__ == "__main__":
    asyncio.run(test_queries())
```

Run it:
```bash
python test_db.py
```

## 🛠️ Useful Commands

### Database Management

```bash
# Check connection
python scripts/db_setup.py check

# Reset database (WARNING: deletes all data)
python scripts/db_setup.py reset

# Seed sample data
python scripts/db_setup.py seed
```

### Alembic Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# Check current version
alembic current
```

### PostgreSQL Commands

```bash
# Connect to database
psql -U trustcapture -d trustcapture_db

# List databases
\l

# List tables
\dt

# Describe table
\d clients

# View table data
SELECT * FROM clients;

# Exit
\q
```

## 🐛 Troubleshooting

### Issue: "psql: error: connection to server on socket"

**Solution:**
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start PostgreSQL
sudo systemctl start postgresql
```

### Issue: "FATAL: password authentication failed"

**Solution:**
```bash
# Reset password
sudo -u postgres psql
ALTER USER trustcapture WITH PASSWORD 'dev_password_123';
\q

# Update .env file with correct password
```

### Issue: "relation does not exist"

**Solution:**
```bash
# Run migrations
alembic upgrade head
```

### Issue: "ImportError: No module named 'app'"

**Solution:**
```bash
# Make sure you're in the backend directory
cd backend

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

## 📚 Documentation

- **Database Schema**: See `DATABASE.md`
- **Implementation Details**: See `DB_IMPLEMENTATION_SUMMARY.md`
- **Task Plan**: See `../.kiro/specs/trust-capture/tasks.md`
- **Requirements**: See `../.kiro/specs/trust-capture/requirements.md`
- **Design**: See `../.kiro/specs/trust-capture/design.md`

## 🎉 Success!

You now have a fully functional TrustCapture database ready for development!

**What's been set up:**
- ✅ PostgreSQL database with 9 tables
- ✅ SQLAlchemy async models
- ✅ Alembic migrations
- ✅ Sample data for testing
- ✅ Helper scripts for database management

**Ready for:**
- ⏭️ Task 3: Authentication implementation
- ⏭️ Task 4: Client management API
- ⏭️ Task 6: Vendor management API
- ⏭️ Task 7: Campaign management API

Happy coding! 🚀
