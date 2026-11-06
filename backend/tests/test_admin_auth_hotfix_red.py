"""P0 admin-endpoint-auth-hotfix - RED tests (reconstructed after worktree loss).

Spec: .kiro/specs/admin-endpoint-auth-hotfix

Property 1 (Bug Condition): the ten administrative routes
  - POST/GET/GET{id}/PUT/DELETE  /api/admin/tenants        (tenants.py)
  - GET depth / GET dead / GET dead/list / POST retry / DELETE  /api/admin/queue  (admin_queue.py)
must reject callers that are NOT an authenticated active platform admin, and a
rejected request must cause NO side effect.

These tests encode the POST-FIX behavior and MUST FAIL on the unmodified base
(routes currently return 2xx + a real side effect). Status codes are pinned to
the confirmed contract (FastAPI 0.109.0 / Starlette 0.35.1):
  - absent Authorization header -> 403 (HTTPBearer auto_error)
  - invalid/expired token, client/vendor JWT (type != admin), inactive admin -> 401

Harness mirrors tests/hotfix_support.py: own NullPool engine, committed seeding,
fail-closed TEST_DATABASE_URL. conftest.py is NOT modified.
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
from app.models.client import Client, SubscriptionTier, SubscriptionStatus
from app.models.vendor import Vendor, VendorStatus
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
        self.client_ids = []
        self.vendor_ids = []
        self.tenant_ids = []
        self.task_ids = []

    async def admin(self, s, active=True):
        a = AdminUser(
            admin_id=uuid.uuid4(), email=f"admin_{uuid.uuid4().hex[:8]}@x.com",
            password_hash=hash_password("x"), name="Admin", is_active=active,
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(a); await s.flush(); self.admin_ids.append(a.admin_id); return a

    async def client(self, s):
        c = Client(
            client_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID,
            email=f"c_{uuid.uuid4().hex[:8]}@x.com", password_hash="x",
            company_name="C", phone_number="+10000000000",
            subscription_tier=SubscriptionTier.FREE, subscription_status=SubscriptionStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(c); await s.flush(); self.client_ids.append(c.client_id); return c

    async def vendor(self, s, creator):
        v = Vendor(
            vendor_id=uuid.uuid4().hex[:6].upper(), tenant_id=DEFAULT_TENANT_ID,
            created_by_client_id=creator.client_id, name="V", phone_number="+919000000000",
            status=VendorStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(v); await s.flush(); self.vendor_ids.append(v.vendor_id); return v

    async def tenant(self, s):
        t = TenantConfig(
            tenant_id=uuid.uuid4(), tenant_name="Victim Tenant",
            subdomain=f"victim-{uuid.uuid4().hex[:8]}", is_active=True,
            primary_color="#111111", secondary_color="#222222",
            email_from_address="a@b.c", email_from_name="n",
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(t); await s.flush(); self.tenant_ids.append(t.tenant_id); return t

    async def dead_task(self, s):
        tk = TaskQueue(
            id=uuid.uuid4(), task_type="process_webhook", payload={"k": "v"},
            status=TaskStatus.DEAD, priority=0, retry_count=3, max_retries=3,
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
            scheduled_at=datetime.now(tz=timezone.utc),
        )
        s.add(tk); await s.flush(); self.task_ids.append(tk.id); return tk

    async def cleanup(self):
        async with TestSessionLocal() as s:
            if self.task_ids:
                await s.execute(delete(TaskQueue).where(TaskQueue.id.in_(self.task_ids)))
            if self.vendor_ids:
                await s.execute(delete(Vendor).where(Vendor.vendor_id.in_(self.vendor_ids)))
            if self.client_ids:
                await s.execute(delete(Client).where(Client.client_id.in_(self.client_ids)))
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


def _client_token(c):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": str(c.client_id), "type": "client", "email": c.email})}


def _vendor_token(v):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": str(v.vendor_id), "type": "vendor", "vendor_id": v.vendor_id})}


def _bad_token():
    return {"Authorization": "Bearer not.a.valid.jwt"}


def _admin_token(a):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": str(a.admin_id), "type": "admin", "email": a.email})}


def _nonadmin_variants(principals):
    c, v, inactive_admin = principals
    # (label, headers, expected status per confirmed contract)
    return [
        ("absent", {}, 403),
        ("bad_token", _bad_token(), 401),
        ("client_jwt", _client_token(c), 401),
        ("vendor_jwt", _vendor_token(v), 401),
        ("inactive_admin", _admin_token(inactive_admin), 401),
    ]


async def _tenant_by_subdomain(sub):
    async with TestSessionLocal() as s:
        return (await s.execute(select(TenantConfig).where(TenantConfig.subdomain == sub))).first()


async def _tenant_state(tid):
    async with TestSessionLocal() as s:
        row = (await s.execute(
            select(TenantConfig.is_active, TenantConfig.tenant_name).where(TenantConfig.tenant_id == tid))).first()
        return (row[0], row[1]) if row else None


async def _task_status(task_id):
    async with TestSessionLocal() as s:
        row = (await s.execute(select(TaskQueue.status).where(TaskQueue.id == task_id))).first()
        return row[0] if row else None


@pytest.mark.asyncio
async def test_tenants_crud_rejects_all_nonadmins_with_no_side_effect(api_client, seeder):
    async with TestSessionLocal() as s:
        c = await seeder.client(s)
        v = await seeder.vendor(s, c)
        inactive = await seeder.admin(s, active=False)
        victim = await seeder.tenant(s)
        await s.commit()

    new_sub = f"attacker-{uuid.uuid4().hex[:8]}"

    for label, hdr, expected in _nonadmin_variants((c, v, inactive)):
        # CREATE (write): must not insert
        r = await api_client.post("/api/admin/tenants", headers=hdr,
                                  json={"tenant_name": "X", "subdomain": new_sub})
        assert r.status_code == expected, f"[create/{label}] {r.status_code} {r.text[:120]}"
        assert await _tenant_by_subdomain(new_sub) is None, f"[create/{label}] tenant was created (leak)"

        # LIST (read)
        r = await api_client.get("/api/admin/tenants", headers=hdr)
        assert r.status_code == expected, f"[list/{label}] {r.status_code}"

        # GET by id (read)
        r = await api_client.get(f"/api/admin/tenants/{victim.tenant_id}", headers=hdr)
        assert r.status_code == expected, f"[get/{label}] {r.status_code}"

        # UPDATE (write): must not change the row
        r = await api_client.put(f"/api/admin/tenants/{victim.tenant_id}", headers=hdr,
                                 json={"tenant_name": "HACKED"})
        assert r.status_code == expected, f"[update/{label}] {r.status_code}"
        assert await _tenant_state(victim.tenant_id) == (True, "Victim Tenant"), f"[update/{label}] tenant modified (leak)"

        # DELETE (soft delete): must not deactivate
        r = await api_client.delete(f"/api/admin/tenants/{victim.tenant_id}", headers=hdr)
        assert r.status_code == expected, f"[delete/{label}] {r.status_code}"
        assert await _tenant_state(victim.tenant_id) == (True, "Victim Tenant"), f"[delete/{label}] tenant deactivated (leak)"


@pytest.mark.asyncio
async def test_queue_routes_reject_all_nonadmins_with_no_side_effect(api_client, seeder):
    async with TestSessionLocal() as s:
        c = await seeder.client(s)
        v = await seeder.vendor(s, c)
        inactive = await seeder.admin(s, active=False)
        dead = await seeder.dead_task(s)
        await s.commit()

    for label, hdr, expected in _nonadmin_variants((c, v, inactive)):
        r = await api_client.get("/api/admin/queue/depth", headers=hdr)
        assert r.status_code == expected, f"[depth/{label}] {r.status_code}"

        r = await api_client.get("/api/admin/queue/dead", headers=hdr)
        assert r.status_code == expected, f"[dead/{label}] {r.status_code}"

        r = await api_client.get("/api/admin/queue/dead/list", headers=hdr)
        assert r.status_code == expected, f"[deadlist/{label}] {r.status_code}"

        # RETRY (write): must not reset to pending
        r = await api_client.post(f"/api/admin/queue/dead/{dead.id}/retry", headers=hdr)
        assert r.status_code == expected, f"[retry/{label}] {r.status_code}"
        assert await _task_status(dead.id) == TaskStatus.DEAD, f"[retry/{label}] task state changed (leak)"

        # DELETE (write): must not remove
        r = await api_client.delete(f"/api/admin/queue/dead/{dead.id}", headers=hdr)
        assert r.status_code == expected, f"[delete/{label}] {r.status_code}"
        assert await _task_status(dead.id) == TaskStatus.DEAD, f"[delete/{label}] dead task removed (leak)"
