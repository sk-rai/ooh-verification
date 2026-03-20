#!/bin/bash
set -e

echo "=== TrustCapture Backend Startup ==="

# Convert DATABASE_URL from postgresql:// to postgresql+asyncpg:// if needed
if [ -n "$DATABASE_URL" ]; then
    # Render provides postgresql:// but SQLAlchemy async needs postgresql+asyncpg://
    export DATABASE_URL=$(echo "$DATABASE_URL" | sed 's|^postgres://|postgresql+asyncpg://|' | sed 's|^postgresql://|postgresql+asyncpg://|')
    echo "Database URL configured (asyncpg)"
fi

# Wait for database to be ready
echo "Waiting for database..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Extract host and port from DATABASE_URL for connectivity check
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:/]*\).*|\1|p')
    DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
    DB_PORT=${DB_PORT:-5432}

    if python3 -c "
import socket
try:
    s = socket.create_connection(('${DB_HOST}', ${DB_PORT}), timeout=5)
    s.close()
    exit(0)
except:
    exit(1)
" 2>/dev/null; then
        echo "Database is reachable at $DB_HOST:$DB_PORT"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for database... attempt $RETRY_COUNT/$MAX_RETRIES"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "WARNING: Could not verify database connectivity, proceeding anyway..."
fi

# Run migrations
echo "Running database migrations..."
python3 -m alembic upgrade head || echo "Migration warning (may be OK if already applied)"

# Seed admin user if not exists
echo "Checking admin user..."
python3 -c "
import asyncio
from app.core.database import async_session_factory, engine
from app.models.admin import AdminUser
from sqlalchemy import select, text

async def seed():
    async with async_session_factory() as session:
        result = await session.execute(select(AdminUser).limit(1))
        if not result.scalar_one_or_none():
            from app.core.security import get_password_hash
            admin = AdminUser(
                email='admin@trustcapture.com',
                hashed_password=get_password_hash('TrustAdmin@2026'),
                full_name='System Admin',
                is_active=True
            )
            session.add(admin)
            await session.commit()
            print('Admin user seeded')
        else:
            print('Admin user exists')

asyncio.run(seed())
" 2>/dev/null || echo "Admin seed skipped (may need manual setup)"

# Start server
echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-2}
