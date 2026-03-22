# Database Migration Issue - Root Cause Analysis

## Problem
Alembic migrations are failing with "type subscriptiontier already exists" error, even though the database appears empty.

## Root Cause
The migration file `20260304_initial_schema.py` has TWO places where enum types are created:

1. **Explicit CREATE TYPE statements** (lines 25-30):
   ```python
   op.execute("CREATE TYPE subscriptiontier AS ENUM (...)")
   ```

2. **Implicit creation by SQLAlchemy** when creating tables with Enum columns:
   ```python
   op.create_table('clients', 
       sa.Column('subscription_tier', postgresql.ENUM(...))
   )
   ```

When SQLAlchemy sees an Enum column, it automatically tries to create the enum type. This conflicts with our explicit CREATE TYPE statements.

## Current State
- Database: Empty (no tables)
- Enum types: Created manually via `setup_db_direct.sql`
- Alembic version: Stamped to `base` (no migrations applied)
- Migration trying to run: `001_initial` → fails because it tries to create enum types that already exist

## Solution Options

### Option A: Remove Explicit CREATE TYPE Statements (RECOMMENDED)
Remove lines 25-30 from `20260304_initial_schema.py` and let SQLAlchemy handle enum creation automatically.

**Pros:**
- SQLAlchemy handles it correctly with checkfirst=True
- Cleaner migration code
- No duplication

**Cons:**
- Need to modify existing migration file

### Option B: Comment Out Enum Creation in Migration
Keep the explicit statements but comment them out since enums already exist.

**Pros:**
- Minimal change
- Preserves history

**Cons:**
- Hacky solution
- Will fail on fresh database

### Option C: Use Raw SQL for Everything
Skip Alembic entirely and use raw SQL scripts.

**Pros:**
- No caching issues
- Full control

**Cons:**
- Lose migration tracking
- Manual version management

## Recommended Action
1. Remove explicit CREATE TYPE statements from `20260304_initial_schema.py` (lines 25-30)
2. Run `python3 -m alembic upgrade head`
3. SQLAlchemy will see the enum types already exist and skip creation

## Commands to Execute
```bash
# Edit the migration file to remove CREATE TYPE statements
# Then run:
python3 -m alembic upgrade head
python3 check_db_status.py
```
