#!/bin/bash
set -e

echo "=== TrustCapture Backend Startup ==="

# Convert DATABASE_URL from postgresql:// to postgresql+asyncpg:// if needed
if [ -n "$DATABASE_URL" ]; then
    export DATABASE_URL=$(echo "$DATABASE_URL" | sed 's|^postgres://|postgresql+asyncpg://|' | sed 's|^postgresql://|postgresql+asyncpg://|')
    echo "Database URL configured (asyncpg)"
fi

# Run migrations directly (skip socket check - Render handles DB availability)
echo "Running database migrations..."
python3 -m alembic upgrade head || echo "Migration warning (may be OK if already applied)"

# Seed admin user if not exists
echo "Checking admin user..."
python3 -c "
import asyncio
from app.core.database import async_session_factory
from app.models.admin import AdminUser
from sqlalchemy import select

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
" 2>&1 || echo "Admin seed skipped"

# Seed default tenant
echo "Checking default tenant..."
python3 -c "
import asyncio
from app.core.database import async_session_factory
from app.models.tenant import TenantConfig
from sqlalchemy import select
import uuid

async def seed():
    async with async_session_factory() as session:
        result = await session.execute(select(TenantConfig).limit(1))
        if not result.scalar_one_or_none():
            tenant = TenantConfig(
                tenant_id=uuid.UUID('e27c6c7a-7f5b-43df-bdc4-abd76ebb99aa'),
                tenant_name='Default Tenant',
                subdomain='default',
                is_active=True
            )
            session.add(tenant)
            await session.commit()
            print('Default tenant seeded')
        else:
            print('Tenant exists')

asyncio.run(seed())
" 2>&1 || echo "Tenant seed skipped"

# Start server
echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-2}
