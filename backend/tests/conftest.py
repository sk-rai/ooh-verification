# Pytest configuration - Using PostgreSQL
import pytest, asyncio, uuid
from typing import AsyncGenerator, Generator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from datetime import datetime, timedelta

from app.main import app
from app.core.database import get_db, Base
from app.models import Client, Vendor, Subscription
from app.models.client import SubscriptionTier, SubscriptionStatus
from app.models.vendor import VendorStatus
from app.core.security import hash_password

# Set environment variable to use mock storage (no external dependencies)
import os
os.environ['USE_MOCK_STORAGE'] = 'true'
os.environ['TESTING'] = 'true'


TEST_DATABASE_URL = 'postgresql+asyncpg://test:test@localhost:5432/test_trustcapture'
test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture(scope='session')
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope='function')
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as session:
        yield session
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope='function')
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url='http://test') as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture
async def test_client(db_session: AsyncSession) -> Client:
    client = Client(
        client_id=uuid.uuid4(), email='test@example.com',
        password_hash=hash_password('TestPass123'), company_name='Test Company',
        phone_number='+1234567890', subscription_tier=SubscriptionTier.FREE,
        subscription_status=SubscriptionStatus.ACTIVE,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow()
    )
    db_session.add(client)
    subscription = Subscription(
        subscription_id=uuid.uuid4(), client_id=client.client_id,
        tier=SubscriptionTier.FREE, status=SubscriptionStatus.ACTIVE,
        photos_quota=50, photos_used=0,
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        created_at=datetime.utcnow(), updated_at=datetime.utcnow()
    )
    db_session.add(subscription)
    await db_session.commit()
    await db_session.refresh(client)
    return client

@pytest.fixture
async def test_vendor(db_session: AsyncSession, test_client: Client) -> Vendor:
    vendor = Vendor(
        vendor_id='TEST01', created_by_client_id=test_client.client_id,
        name='Test Vendor', phone_number='+1987654321',
        email='vendor@example.com', status=VendorStatus.ACTIVE,
        device_id='test-device-123',
        created_at=datetime.utcnow(), updated_at=datetime.utcnow()
    )
    db_session.add(vendor)
    await db_session.commit()
    await db_session.refresh(vendor)
    return vendor

@pytest.fixture
async def client_token(client: AsyncClient, test_client: Client) -> str:
    response = await client.post('/api/auth/login', json={'email': 'test@example.com', 'password': 'TestPass123'})
    assert response.status_code == 200
    return response.json()['access_token']

@pytest.fixture
def auth_headers(client_token: str) -> dict:
    return {'Authorization': f'Bearer {client_token}'}

# Alias for test_client (used by photo upload tests)
@pytest.fixture
async def test_client_user(test_client: Client) -> Client:
    return test_client
