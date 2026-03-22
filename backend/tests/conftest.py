"""Test configuration and fixtures for TrustCapture backend tests."""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

os.environ["TESTING"] = "true"
os.environ["USE_MOCK_STORAGE"] = "true"

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.client import Client, SubscriptionTier, SubscriptionStatus
from app.models.vendor import Vendor, VendorStatus
from app.models.campaign import Campaign, CampaignType, CampaignStatus
from app.models.subscription import Subscription
from app.models.tenant_config import TenantConfig
from app.models.audit_log import AuditLog
from app.models.photo import Photo, VerificationStatus
from app.models.sensor_data import SensorData
from app.models.photo_signature import PhotoSignature
from app.models.location_profile import LocationProfile
from app.models.campaign_vendor_assignment import CampaignVendorAssignment
from app.models.admin_user import AdminUser

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_test"
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

DEFAULT_TENANT_ID = uuid.UUID("e27c6c7a-7f5b-43df-bdc4-abd76ebb99aa")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Create all tables before running tests."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest_asyncio.fixture(scope="function")
async def test_tenant(db_session: AsyncSession) -> TenantConfig:
    tenant = TenantConfig(
        tenant_id=DEFAULT_TENANT_ID,
        tenant_name="Test Tenant",
        subdomain="default",
        branding_primary_color="#007bff",
        branding_secondary_color="#6c757d",
        email_from_address="noreply@test.trustcapture.com",
        email_from_name="TrustCapture Test",
        is_active=True,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest_asyncio.fixture(scope="function")
async def test_client_user(db_session: AsyncSession, test_tenant: TenantConfig) -> Client:
    client = Client(
        client_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email="test@example.com",
        password_hash=hash_password("Test123!@#"),
        company_name="Test Company",
        phone_number="+1234567890",
        subscription_tier=SubscriptionTier.FREE,
        subscription_status=SubscriptionStatus.ACTIVE,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    db_session.add(client)
    await db_session.flush()
    return client


@pytest_asyncio.fixture(scope="function")
async def test_subscription(db_session: AsyncSession, test_client_user: Client, test_tenant: TenantConfig) -> Subscription:
    sub = Subscription(
        subscription_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        client_id=test_client_user.client_id,
        tier=SubscriptionTier.FREE,
        status=SubscriptionStatus.ACTIVE,
        start_date=datetime.now(tz=timezone.utc),
        end_date=datetime.now(tz=timezone.utc) + timedelta(days=30),
        current_period_start=datetime.now(tz=timezone.utc),
        current_period_end=datetime.now(tz=timezone.utc) + timedelta(days=30),
        campaigns_quota=100,
        campaigns_used=0,
        vendors_quota=100,
        vendors_used=0,
        photos_quota=1000,
        photos_used=0,
        storage_quota_mb=10000,
        storage_used_mb=0,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    db_session.add(sub)
    await db_session.flush()
    return sub


@pytest_asyncio.fixture(scope="function")
async def test_vendor(db_session: AsyncSession, test_client_user: Client, test_tenant: TenantConfig) -> Vendor:
    vendor = Vendor(
        vendor_id=f"VND{uuid.uuid4().hex[:3].upper()}",
        tenant_id=test_tenant.tenant_id,
        created_by_client_id=test_client_user.client_id,
        name="Test Vendor",
        phone_number="+919876543210",
        email="vendor@example.com",
        status=VendorStatus.ACTIVE,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    db_session.add(vendor)
    await db_session.flush()
    return vendor


@pytest_asyncio.fixture(scope="function")
async def test_campaign(db_session: AsyncSession, test_client_user: Client, test_tenant: TenantConfig) -> Campaign:
    campaign = Campaign(
        campaign_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        client_id=test_client_user.client_id,
        campaign_code=f"CAM-TEST-{uuid.uuid4().hex[:4].upper()}",
        name="Test Campaign",
        campaign_type=CampaignType.OOH,
        start_date=datetime.now(tz=timezone.utc),
        end_date=datetime.now(tz=timezone.utc) + timedelta(days=30),
        status=CampaignStatus.ACTIVE,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    db_session.add(campaign)
    await db_session.flush()
    return campaign


@pytest_asyncio.fixture(scope="function")
async def test_admin(db_session: AsyncSession) -> AdminUser:
    admin = AdminUser(
        admin_id=uuid.uuid4(),
        email="admin@trustcapture.com",
        password_hash=hash_password("TrustAdmin@2026"),
        full_name="Test Admin",
        is_active=True,
        created_at=datetime.now(tz=timezone.utc),
    )
    db_session.add(admin)
    await db_session.flush()
    return admin


@pytest_asyncio.fixture(scope="function")
async def auth_headers(test_client_user: Client, test_tenant: TenantConfig) -> dict:
    token = create_access_token(data={"sub": str(test_client_user.client_id), "type": "client", "email": test_client_user.email})
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(test_tenant.tenant_id)}


@pytest_asyncio.fixture(scope="function")
async def vendor_auth_headers(test_vendor: Vendor, test_client_user: Client, test_tenant: TenantConfig) -> dict:
    token = create_access_token(data={"sub": str(test_client_user.client_id), "type": "vendor", "vendor_id": test_vendor.vendor_id})
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(test_tenant.tenant_id)}


@pytest_asyncio.fixture(scope="function")
async def admin_auth_headers(test_admin: AdminUser) -> dict:
    token = create_access_token(data={"sub": str(test_admin.admin_id), "type": "admin", "email": test_admin.email})
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(DEFAULT_TENANT_ID)}


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
