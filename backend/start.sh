#!/bin/bash
set -e

echo "=== TrustCapture Backend Startup ==="

if [ -n "$DATABASE_URL" ]; then
    export DATABASE_URL=$(echo "$DATABASE_URL" | sed 's|^postgres://|postgresql+asyncpg://|' | sed 's|^postgresql://|postgresql+asyncpg://|')
    echo "Database URL configured (asyncpg)"
fi

echo "Running database migrations..."
python3 -m alembic upgrade head || echo "Migration warning (may be OK if already applied)"

echo "Checking admin user..."
python3 << 'SEEDEOF'
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.admin_user import AdminUser
from app.core.security import hash_password
from sqlalchemy import select

async def seed():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AdminUser).limit(1))
        if not result.scalar_one_or_none():
            admin = AdminUser(
                email="admin@trustcapture.com",
                password_hash=hash_password("TrustAdmin@2026"),
                name="System Admin",
                is_active=True
            )
            session.add(admin)
            await session.commit()
            print("Admin user seeded")
        else:
            print("Admin user exists")

asyncio.run(seed())
SEEDEOF
echo "Admin seed done" || echo "Admin seed skipped"

echo "Checking default tenant..."
python3 << 'TENANTEOF'
import asyncio, uuid
from app.core.database import AsyncSessionLocal
from app.models.tenant_config import TenantConfig
from sqlalchemy import select

async def seed():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(TenantConfig).limit(1))
        if not result.scalar_one_or_none():
            tenant = TenantConfig(
                tenant_id=uuid.UUID("e27c6c7a-7f5b-43df-bdc4-abd76ebb99aa"),
                tenant_name="Default Tenant",
                subdomain="default",
                is_active=True
            )
            session.add(tenant)
            await session.commit()
            print("Default tenant seeded")
        else:
            print("Tenant exists")

asyncio.run(seed())
TENANTEOF
echo "Tenant seed done" || echo "Tenant seed skipped"

echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-2}
