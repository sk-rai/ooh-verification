"""
Stable Test Configuration and Fixtures for TrustCapture Backend Tests

This conftest provides fixtures for all test suites with proper async handling,
database isolation, and multi-tenancy support.
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from faker import Faker
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.client import Client
from app.models.vendor import Vendor
from app.models.campaign import Campaign
from app.models.subscription import Subscription
from app.models.tenant_config import TenantConfig
from app.models.audit_log import AuditLog
from app.models.photo import Photo
from app.models.location_profile import LocationProfile

# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_test"
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Create all tables before running tests and drop them after."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test with proper cleanup."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True, poolclass=None)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_tenant(db_session: AsyncSession) -> TenantConfig:
    """Create or retrieve test tenant configuration."""
    tenant_id = uuid.UUID("e27c6c7a-7f5b-43df-bdc4-abd76ebb99aa")
    
    # Check if tenant already exists
    stmt = text("SELECT * FROM tenant_config WHERE tenant_id = :tenant_id")
    result = await db_session.execute(stmt, {"tenant_id": str(tenant_id)})
    existing = result.first()
    
    if existing:
        # Return existing tenant
        from sqlalchemy import select
        stmt = select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
        result = await db_session.execute(stmt)
        return result.scalar_one()
    
    # Create new tenant
    tenant = TenantConfig(
        tenant_id=tenant_id,
        tenant_name="Test Tenant",
        subdomain="test",
        custom_domain=None,
        logo_url=None,
        primary_color="#007bff",
        secondary_color="#6c757d",
        email_from_address="noreply@test.trustcapture.com",
        email_from_name="TrustCapture Test",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest_asyncio.fixture(scope="function")
async def test_client_user(db_session: AsyncSession, test_tenant: TenantConfig) -> Client:
    """Create a test client user."""
    # Check if client already exists
    from sqlalchemy import select
    stmt = select(Client).where(Client.email == "test@example.com")
    result = await db_session.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        return existing
    
    client = Client(
        client_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email="test@example.com",
        password_hash=hash_password("Test123!@#"),
        company_name="Test Company",
        phone_number="+1234567890",
        subscription_tier="free",
        subscription_status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture(scope="function")
async def test_client(test_client_user: Client) -> Client:
    """Alias for test_client_user for backward compatibility."""
    return test_client_user


@pytest_asyncio.fixture(scope="function")
async def test_subscription(
    db_session: AsyncSession, 
    test_client_user: Client, 
    test_tenant: TenantConfig
) -> Subscription:
    """Create a test subscription."""
    subscription = Subscription(
        subscription_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        client_id=test_client_user.client_id,
        tier="free",
        status="active",
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        campaigns_quota=5,
        campaigns_used=0,
        vendors_quota=10,
        vendors_used=0,
        photos_quota=100,
        photos_used=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(subscription)
    await db_session.commit()
    await db_session.refresh(subscription)
    return subscription


@pytest_asyncio.fixture(scope="function")
async def test_vendor(
    db_session: AsyncSession, 
    test_client_user: Client, 
    test_tenant: TenantConfig
) -> Vendor:
    """Create a test vendor."""
    vendor = Vendor(
        vendor_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        client_id=test_client_user.client_id,
        vendor_code=f"VND{uuid.uuid4().hex[:6].upper()}",
        name="Test Vendor",
        phone_number="+1234567890",
        email="vendor@example.com",
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(vendor)
    await db_session.commit()
    await db_session.refresh(vendor)
    return vendor


@pytest_asyncio.fixture(scope="function")
async def test_campaign(
    db_session: AsyncSession, 
    test_client_user: Client, 
    test_tenant: TenantConfig
) -> Campaign:
    """Create a test campaign."""
    campaign = Campaign(
        campaign_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        client_id=test_client_user.client_id,
        campaign_code=f"CAMP{uuid.uuid4().hex[:6].upper()}",
        name="Test Campaign",
        campaign_type="billboard",
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(campaign)
    await db_session.commit()
    await db_session.refresh(campaign)
    return campaign


@pytest_asyncio.fixture(scope="function")
async def auth_headers(test_client_user: Client, test_tenant: TenantConfig) -> dict:
    """Create authentication headers with JWT token."""
    access_token = create_access_token(
        data={"sub": str(test_client_user.client_id), "type": "client"}
    )
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Tenant-ID": str(test_tenant.tenant_id)
    }


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing (named 'client')."""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing (named 'async_client')."""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def client_token(
    client: AsyncClient, 
    test_client_user: Client, 
    test_tenant: TenantConfig
) -> str:
    """Get authentication token for test client."""
    access_token = create_access_token(
        data={"sub": str(test_client_user.client_id), "type": "client"}
    )
    return access_token


@pytest.fixture(scope="session")
def faker() -> Faker:
    """Create a Faker instance for generating test data."""
    return Faker()
