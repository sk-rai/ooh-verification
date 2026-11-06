"""P0 admin-endpoint-auth-hotfix - preservation tests (reconstructed after worktree loss).

Property 2 (Preservation): an authenticated ACTIVE admin retains existing
behavior on the ten admin routes, and GET /api/branding stays PUBLIC. Observed
on the UNMODIFIED base so the fix must preserve it.

Harness mirrors tests/hotfix_support.py. conftest.py is NOT modified.
"""
import os
import uuid
from datetime import datetime, timezone

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("USE_MOCK_STORAGE", "true")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.admin_user import AdminUser
from app.models.tenant_config import TenantConfig
from app.models.task_queue import TaskQueue, TaskStatus

from tests.hotfix_support import TEST_DATABASE_URL, DEFAULT_TENANT_ID, hotfix_runtime_env  # noqa: F401

_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def api_client() -> AsyncClient:
    async def override_get_db():
        async with TestSessionLocal() as s:
            yield s
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


class _Seeder:
    def __init__(self):
        self.admin_ids = []
        self.tenant_ids = []
        self.task_ids = []

    async def admin(self, s):
        a = AdminUser(
            admin_id=uuid.uuid4(), email=f"admin_{uuid.uuid4().hex[:8]}@x.com",
            password_hash=hash_password("x"), name="Admin", is_active=True,
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(a); await s.flush(); self.admin_ids.append(a.admin_id); return a

    async def dead_task(self):
        async with TestSessionLocal() as s:
            tk = TaskQueue(
                id=uuid.uuid4(), task_type="process_webhook", payload={"k": "v"},
                status=TaskStatus.DEAD, priority=0, retry_count=3, max_retries=3,
                created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
                scheduled_at=datetime.now(tz=timezone.utc),
            )
            s.add(tk); self.task_ids.append(tk.id); await s.commit()
            return tk.id

    def track_tenant(self, tenant_id):
        self.tenant_ids.append(tenant_id)

    async def cleanup(self):
        async with TestSessionLocal() as s:
            if self.task_ids:
                await s.execute(delete(TaskQueue).where(TaskQueue.id.in_(self.task_ids)))
            if self.tenant_ids:
                await s.execute(delete(TenantConfig).where(TenantConfig.tenant_id.in_(self.tenant_ids)))
            if self.admin_ids:
                await s.execute(delete(AdminUser).where(AdminUser.admin_id.in_(self.admin_ids)))
            await s.commit()


@pytest_asyncio.fixture
async def seeder():
    sd = _Seeder()
    yield sd
    await sd.cleanup()


async def _admin_headers(seeder):
    async with TestSessionLocal() as s:
        a = await seeder.admin(s)
        await s.commit()
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": str(a.admin_id), "type": "admin", "email": a.email})}


@pytest.mark.asyncio
async def test_branding_is_public_unauthenticated(api_client):
    r = await api_client.get("/api/branding")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "tenant_name" in body and "primary_color" in body


@pytest.mark.asyncio
async def test_active_admin_tenant_crud_preserved(api_client, seeder):
    hdr = await _admin_headers(seeder)
    sub = f"pres-{uuid.uuid4().hex[:8]}"

    r = await api_client.post("/api/admin/tenants", headers=hdr,
                              json={"tenant_name": "Pres", "subdomain": sub})
    assert r.status_code == 201, r.text
    created = r.json()
    tid = created["tenant_id"]
    seeder.track_tenant(uuid.UUID(tid))
    assert created["tenant_name"] == "Pres" and created["subdomain"] == sub
    assert created["is_active"] is True

    r = await api_client.get("/api/admin/tenants", headers=hdr)
    assert r.status_code == 200, r.text
    assert set(r.json().keys()) >= {"tenants", "total"}

    r = await api_client.get(f"/api/admin/tenants/{tid}", headers=hdr)
    assert r.status_code == 200 and r.json()["tenant_id"] == tid

    r = await api_client.put(f"/api/admin/tenants/{tid}", headers=hdr, json={"tenant_name": "Pres2"})
    assert r.status_code == 200 and r.json()["tenant_name"] == "Pres2"

    r = await api_client.delete(f"/api/admin/tenants/{tid}", headers=hdr)
    assert r.status_code == 204, r.text
    async with TestSessionLocal() as s:
        active = (await s.execute(
            select(TenantConfig.is_active).where(TenantConfig.tenant_id == uuid.UUID(tid)))).scalar()
    assert active is False


@pytest.mark.asyncio
async def test_active_admin_queue_reads_preserved(api_client, seeder):
    hdr = await _admin_headers(seeder)
    await seeder.dead_task()

    r = await api_client.get("/api/admin/queue/depth", headers=hdr)
    assert r.status_code == 200 and "pending" in r.json()

    r = await api_client.get("/api/admin/queue/dead", headers=hdr)
    assert r.status_code == 200 and "dead" in r.json()

    r = await api_client.get("/api/admin/queue/dead/list", headers=hdr)
    assert r.status_code == 200 and "tasks" in r.json()


@pytest.mark.asyncio
async def test_active_admin_queue_retry_and_delete_preserved(api_client, seeder):
    hdr = await _admin_headers(seeder)

    retry_id = await seeder.dead_task()
    r = await api_client.post(f"/api/admin/queue/dead/{retry_id}/retry", headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "retried"
    async with TestSessionLocal() as s:
        st = (await s.execute(select(TaskQueue.status).where(TaskQueue.id == retry_id))).scalar()
    assert st == TaskStatus.PENDING

    del_id = await seeder.dead_task()
    r = await api_client.delete(f"/api/admin/queue/dead/{del_id}", headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "deleted"
    async with TestSessionLocal() as s:
        exists = (await s.execute(select(TaskQueue.id).where(TaskQueue.id == del_id))).first()
    assert exists is None
