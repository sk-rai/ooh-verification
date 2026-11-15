"""
Hotfix 2 security RED tests: evidence isolation and tenant header enforcement.

Tests assert SECURE behavior: fail on the vulnerable baseline, pass after fix.
Uses hotfix_support.py fail-closed DB isolation.
"""
import os
import uuid
from datetime import datetime, timezone

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("USE_MOCK_STORAGE", "true")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from tests.hotfix_support import TEST_DATABASE_URL, DEFAULT_TENANT_ID, hotfix_runtime_env  # noqa: F401
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.vendor import Vendor, VendorStatus
from app.models.client import Client, SubscriptionTier, SubscriptionStatus
from app.models.tenant_config import TenantConfig
from app.models.evidence import Evidence

_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool)
_Sessions = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

VICTIM_TENANT_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


@pytest_asyncio.fixture(autouse=True)
async def _ensure_victim_tenant(setup_test_database):
    async with _Sessions() as s:
        existing = (await s.execute(
            select(TenantConfig.tenant_id).where(TenantConfig.tenant_id == VICTIM_TENANT_ID)
        )).scalar_one_or_none()
        if not existing:
            s.add(TenantConfig(
                tenant_id=VICTIM_TENANT_ID,
                tenant_name="Victim Tenant",
                subdomain=f"victim-hf2-{VICTIM_TENANT_ID.hex[:6]}",
                primary_color="#ff0000",
                secondary_color="#ff0000",
                email_from_address="victim@test.invalid",
                email_from_name="Victim",
                is_active=True,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            ))
            await s.commit()


@pytest_asyncio.fixture
async def api_client():
    async def _override():
        async with _Sessions() as s:
            yield s
    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def attacker_vendor(attacker_client):
    """Vendor owned by attacker_client, in DEFAULT_TENANT_ID."""
    v = Vendor(
        vendor_id=uuid.uuid4().hex[:6].upper(),
        tenant_id=DEFAULT_TENANT_ID,
        created_by_client_id=attacker_client.client_id,
        name="Attacker Vendor",
        phone_number="+919000000099",
        status=VendorStatus.ACTIVE,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    async with _Sessions() as s:
        s.add(v); await s.commit()
    yield v
    async with _Sessions() as s:
        await s.execute(delete(Vendor).where(Vendor.vendor_id == v.vendor_id))
        await s.commit()


@pytest_asyncio.fixture
async def attacker_client():
    c = Client(
        client_id=uuid.uuid4(),
        tenant_id=DEFAULT_TENANT_ID,
        email=f"attacker_{uuid.uuid4().hex[:8]}@test.invalid",
        password_hash=hash_password("AttackerPass!1"),
        company_name="Attacker Co",
        phone_number="+10000000003",
        subscription_tier=SubscriptionTier.FREE,
        subscription_status=SubscriptionStatus.ACTIVE,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    async with _Sessions() as s:
        s.add(c); await s.commit()
    yield c
    async with _Sessions() as s:
        await s.execute(delete(Client).where(Client.client_id == c.client_id))
        await s.commit()


@pytest_asyncio.fixture
async def victim_evidence():
    """A piece of evidence belonging to VICTIM_TENANT_ID.

    Builds the full FK chain required by the schema:
    victim Client -> victim Vendor -> Evidence, all inside VICTIM_TENANT_ID.
    """
    victim_client = Client(
        client_id=uuid.uuid4(),
        tenant_id=VICTIM_TENANT_ID,
        email=f"victim_{uuid.uuid4().hex[:8]}@test.invalid",
        password_hash=hash_password("VictimPass!1"),
        company_name="Victim Co",
        phone_number="+10000000009",
        subscription_tier=SubscriptionTier.FREE,
        subscription_status=SubscriptionStatus.ACTIVE,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    victim_vendor = Vendor(
        vendor_id=uuid.uuid4().hex[:6].upper(),
        tenant_id=VICTIM_TENANT_ID,
        created_by_client_id=victim_client.client_id,
        name="Victim Vendor",
        phone_number="+919000000011",
        status=VendorStatus.ACTIVE,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    ev = Evidence(
        tenant_id=VICTIM_TENANT_ID,
        vendor_id=victim_vendor.vendor_id,
        evidence_type="text_note",
        text_content="victim secret note",
        verification_status="pending",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    async with _Sessions() as s:
        s.add(victim_client)
        s.add(victim_vendor)
        s.add(ev)
        await s.commit()
        await s.refresh(ev)
    yield ev
    async with _Sessions() as s:
        await s.execute(delete(Evidence).where(Evidence.evidence_id == ev.evidence_id))
        await s.execute(delete(Vendor).where(Vendor.vendor_id == victim_vendor.vendor_id))
        await s.execute(delete(Client).where(Client.client_id == victim_client.client_id))
        await s.commit()


def _vendor_headers(vendor, tenant_id=None):
    token = create_access_token({
        "sub": str(vendor.vendor_id), "type": "vendor", "vendor_id": vendor.vendor_id
    })
    hdr = {"Authorization": f"Bearer {token}"}
    if tenant_id:
        hdr["X-Tenant-ID"] = str(tenant_id)
    return hdr


def _client_headers(client, tenant_id=None):
    token = create_access_token({
        "sub": str(client.client_id), "type": "client", "email": client.email
    })
    hdr = {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant_id or DEFAULT_TENANT_ID)}
    return hdr


# ─── Evidence read: unauthenticated ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_evidence_get_rejects_anonymous(api_client, victim_evidence):
    """GET /api/evidence/{id} must reject unauthenticated callers."""
    resp = await api_client.get(
        f"/api/evidence/{victim_evidence.evidence_id}",
        headers={"X-Tenant-ID": str(VICTIM_TENANT_ID)},
    )
    assert resp.status_code in (401, 403), (
        f"unauthenticated evidence read returned {resp.status_code} — vulnerable"
    )


@pytest.mark.asyncio
async def test_evidence_distance_rejects_anonymous(api_client):
    """GET /api/evidence/distance must reject unauthenticated callers."""
    resp = await api_client.get(
        f"/api/evidence/distance?id1={uuid.uuid4()}&id2={uuid.uuid4()}",
        headers={"X-Tenant-ID": str(DEFAULT_TENANT_ID)},
    )
    assert resp.status_code in (401, 403), (
        f"unauthenticated /evidence/distance returned {resp.status_code} — vulnerable"
    )


@pytest.mark.asyncio
async def test_evidence_route_analysis_rejects_anonymous(api_client):
    """GET /api/evidence/route-analysis must reject unauthenticated callers."""
    resp = await api_client.get(
        "/api/evidence/route-analysis",
        headers={"X-Tenant-ID": str(DEFAULT_TENANT_ID)},
    )
    assert resp.status_code in (401, 403), (
        f"unauthenticated /evidence/route-analysis returned {resp.status_code} — vulnerable"
    )


# ─── Evidence read: cross-tenant ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evidence_get_rejects_cross_tenant(api_client, attacker_client, victim_evidence):
    """Authenticated client cannot read evidence from another tenant via X-Tenant-ID."""
    resp = await api_client.get(
        f"/api/evidence/{victim_evidence.evidence_id}",
        headers=_client_headers(attacker_client, VICTIM_TENANT_ID),
    )
    assert resp.status_code in (401, 403, 404), (
        f"cross-tenant evidence read returned {resp.status_code} — vulnerable"
    )


# ─── Evidence upload: cross-tenant ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_evidence_upload_rejects_cross_tenant_header(api_client, attacker_vendor):
    """POST /api/evidence/upload with cross-tenant header must be rejected."""
    resp = await api_client.post(
        "/api/evidence/upload",
        data={"evidence_type": "text_note", "text_content": "attack"},
        headers=_vendor_headers(attacker_vendor, VICTIM_TENANT_ID),
    )
    assert resp.status_code in (400, 401, 403, 422), (
        f"cross-tenant upload returned {resp.status_code} — vulnerable"
    )


# ─── Tracks sync: cross-tenant ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tracks_sync_rejects_cross_tenant_header(api_client, attacker_vendor):
    """POST /api/tracks/sync with cross-tenant header must be rejected."""
    resp = await api_client.post(
        "/api/tracks/sync",
        json={"points": [{"lat": 0, "lon": 0, "timestamp_ms": 1000}]},
        headers=_vendor_headers(attacker_vendor, VICTIM_TENANT_ID),
    )
    assert resp.status_code in (400, 401, 403), (
        f"cross-tenant tracks/sync returned {resp.status_code} — vulnerable"
    )


# ─── Tracks read: cross-tenant header ───────────────────────────────────────

@pytest.mark.asyncio
async def test_tracks_summary_rejects_conflicting_tenant_header(api_client, attacker_client):
    """GET /api/tracks/summary with mismatched X-Tenant-ID must be rejected."""
    resp = await api_client.get(
        "/api/tracks/summary?start_date=2026-01-01&end_date=2026-01-31",
        headers=_client_headers(attacker_client, VICTIM_TENANT_ID),
    )
    assert resp.status_code in (400, 401, 403), (
        f"cross-tenant tracks/summary returned {resp.status_code} — vulnerable"
    )


@pytest.mark.asyncio
async def test_tracks_vendor_rejects_conflicting_tenant_header(api_client, attacker_client):
    """GET /api/tracks/vendor/{id} with mismatched X-Tenant-ID must be rejected."""
    resp = await api_client.get(
        f"/api/tracks/vendor/SOMEVENDOR?date=2026-01-01",
        headers=_client_headers(attacker_client, VICTIM_TENANT_ID),
    )
    assert resp.status_code in (400, 401, 403), (
        f"cross-tenant tracks/vendor returned {resp.status_code} — vulnerable"
    )


# ─── Public routes still work ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_public_branding_still_accessible(api_client):
    resp = await api_client.get("/api/branding")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_analytics_track_still_public(api_client):
    resp = await api_client.post(
        "/api/analytics/track",
        json={"page": "/test"},
        headers={"X-Tenant-ID": str(DEFAULT_TENANT_ID)},
    )
    assert resp.status_code == 200


# ─── Evidence helper: seed an own-tenant evidence item for the attacker client ──

@pytest_asyncio.fixture
async def attacker_evidence(attacker_client, attacker_vendor):
    """Evidence owned by the attacker's OWN tenant (DEFAULT_TENANT_ID), with GPS,
    so positive same-tenant distance/route-analysis can be exercised.

    The items are campaign-free (Quick Capture). Under the shared Evidence visibility rule a
    client owns Quick Capture only through an ACTIVE vendor-client association, so the
    fixture creates that association (the normal state for a client's own vendor).
    """
    from app.models.vendor_client_association import VendorClientAssociation, AssociationStatus
    assoc = VendorClientAssociation(
        association_id=uuid.uuid4(), vendor_id=attacker_vendor.vendor_id,
        client_id=attacker_client.client_id, tenant_id=DEFAULT_TENANT_ID,
        status=AssociationStatus.ACTIVE, enrolled_at=datetime.now(tz=timezone.utc),
    )
    ev = Evidence(
        tenant_id=DEFAULT_TENANT_ID,
        vendor_id=attacker_vendor.vendor_id,
        evidence_type="photo",
        verification_status="pending",
        latitude=19.0760,
        longitude=72.8777,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    ev2 = Evidence(
        tenant_id=DEFAULT_TENANT_ID,
        vendor_id=attacker_vendor.vendor_id,
        evidence_type="photo",
        verification_status="pending",
        latitude=19.2183,
        longitude=72.9781,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    async with _Sessions() as s:
        s.add(assoc); s.add(ev); s.add(ev2); await s.commit()
        await s.refresh(ev); await s.refresh(ev2)
    yield (ev, ev2)
    async with _Sessions() as s:
        await s.execute(delete(Evidence).where(Evidence.evidence_id.in_([ev.evidence_id, ev2.evidence_id])))
        await s.execute(delete(VendorClientAssociation).where(
            VendorClientAssociation.association_id == assoc.association_id))
        await s.commit()


# ─── Route-ordering: /distance and /route-analysis are now REACHABLE handlers ───

@pytest.mark.asyncio
async def test_distance_rejects_anonymous_reachable(api_client):
    """After route reorder, /distance resolves to its own handler and the auth
    dependency fires (401/403), NOT a 422 from the shadowing {evidence_id} route."""
    resp = await api_client.get(
        f"/api/evidence/distance?id1={uuid.uuid4()}&id2={uuid.uuid4()}",
    )
    assert resp.status_code in (401, 403), (
        f"/distance anonymous returned {resp.status_code} — expected auth rejection"
    )


@pytest.mark.asyncio
async def test_route_analysis_rejects_anonymous_reachable(api_client):
    resp = await api_client.get("/api/evidence/route-analysis")
    assert resp.status_code in (401, 403), (
        f"/route-analysis anonymous returned {resp.status_code} — expected auth rejection"
    )


@pytest.mark.asyncio
async def test_distance_rejects_cross_tenant_header(api_client, attacker_client):
    resp = await api_client.get(
        f"/api/evidence/distance?id1={uuid.uuid4()}&id2={uuid.uuid4()}",
        headers=_client_headers(attacker_client, VICTIM_TENANT_ID),
    )
    assert resp.status_code == 403, (
        f"/distance cross-tenant header returned {resp.status_code} — expected 403"
    )


@pytest.mark.asyncio
async def test_route_analysis_rejects_cross_tenant_header(api_client, attacker_client):
    resp = await api_client.get(
        "/api/evidence/route-analysis",
        headers=_client_headers(attacker_client, VICTIM_TENANT_ID),
    )
    assert resp.status_code == 403, (
        f"/route-analysis cross-tenant header returned {resp.status_code} — expected 403"
    )


# ─── Positive same-tenant: newly-reachable handlers serve the owner's own data ──

@pytest.mark.asyncio
async def test_distance_same_tenant_ok(api_client, attacker_client, attacker_evidence):
    ev1, ev2 = attacker_evidence
    resp = await api_client.get(
        f"/api/evidence/distance?id1={ev1.evidence_id}&id2={ev2.evidence_id}",
        headers=_client_headers(attacker_client),  # matching DEFAULT_TENANT_ID
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("distance_meters") is not None and body["distance_meters"] > 0


@pytest.mark.asyncio
async def test_route_analysis_same_tenant_ok(api_client, attacker_client, attacker_evidence):
    ev1, _ = attacker_evidence
    resp = await api_client.get(
        f"/api/evidence/route-analysis?vendor_id={ev1.vendor_id}",
        headers=_client_headers(attacker_client),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "points" in body and body["total_points"] >= 1


@pytest.mark.asyncio
async def test_evidence_detail_same_tenant_still_works(api_client, attacker_client, attacker_evidence):
    """Regression: the parameterized /{evidence_id} read still works for the owner."""
    ev1, _ = attacker_evidence
    resp = await api_client.get(
        f"/api/evidence/{ev1.evidence_id}",
        headers=_client_headers(attacker_client),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["evidence_id"] == str(ev1.evidence_id)


# ─── Report-email /settings: authenticated, principal-scoped, header cannot cross ─

@pytest.mark.asyncio
async def test_report_settings_get_rejects_anonymous(api_client):
    resp = await api_client.get("/api/reports/email/settings")
    assert resp.status_code in (401, 403), (
        f"/reports/email/settings GET anonymous returned {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_report_settings_post_rejects_anonymous(api_client):
    resp = await api_client.post(
        "/api/reports/email/settings",
        json={"enabled": True, "recipients": ["x@test.invalid"], "frequency": "daily"},
    )
    assert resp.status_code in (401, 403), (
        f"/reports/email/settings POST anonymous returned {resp.status_code}"
    )


class _CapturingResult:
    """Mimics the SQLAlchemy Result surface used by get_current_client (ORM:
    scalar_one_or_none) and by the settings handlers (text: fetchone)."""
    def __init__(self, *, scalar=None, row=None):
        self._scalar = scalar
        self._row = row
    def scalar_one_or_none(self):
        return self._scalar
    def fetchone(self):
        return self._row


class _CapturingSession:
    """Controlled DB mock: records (sql_text, params) for every execute() and
    returns canned results. Satisfies get_current_client's ORM Client lookup
    (returns the supplied principal) AND the settings text() SQL, so tests can
    assert exactly which client_id was bound. Touches NO real database."""
    def __init__(self, principal=None, settings_row=None):
        self.calls = []                 # list of (lowered_sql, params_dict)
        self._principal = principal     # Client returned to get_current_client
        self._settings_row = settings_row
    async def execute(self, statement, params=None):
        sql = str(statement)
        low = sql.lower()
        self.calls.append((low, dict(params or {})))
        # get_current_client issues an ORM SELECT on the clients table.
        if low.strip().startswith("select") and "from clients" in low and "report_settings" not in low:
            return _CapturingResult(scalar=self._principal)
        # settings GET: SELECT report_settings FROM clients WHERE client_id = :cid
        if "report_settings" in low and low.strip().startswith("select"):
            return _CapturingResult(row=self._settings_row)
        return _CapturingResult()
    async def commit(self):
        self.calls.append(("<commit>", {}))


@pytest.mark.asyncio
async def test_report_settings_get_uses_principal_client_id(attacker_client):
    """GET /settings binds the SQL to the authenticated client's client_id, and a
    conflicting X-Tenant-ID does not change which client_id is queried."""
    cap = _CapturingSession(principal=attacker_client,
                            settings_row=({"enabled": True, "recipients": ["mine@test.invalid"], "frequency": "weekly"},))

    # get_current_client resolves identity from the JWT via a real session; we
    # override get_db to the capturing session so the handler body is observed.
    async def _override():
        yield cap
    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = dict(_client_headers(attacker_client))
            headers["X-Tenant-ID"] = str(VICTIM_TENANT_ID)  # conflicting on purpose
            resp = await ac.get("/api/reports/email/settings", headers=headers)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200, resp.text
    # The SELECT must have been bound to the PRINCIPAL's client_id — never a tenant id.
    select_calls = [c for c in cap.calls if c[0].strip().startswith("select")]
    assert select_calls, "no SELECT issued"
    bound = select_calls[-1][1]
    assert bound.get("cid") == str(attacker_client.client_id), (
        f"settings SELECT used cid={bound.get('cid')} — expected principal "
        f"{attacker_client.client_id}; header tenant must NOT redirect the query"
    )
    assert str(VICTIM_TENANT_ID) not in bound.values()
    assert resp.json()["recipients"] == ["mine@test.invalid"]


@pytest.mark.asyncio
async def test_report_settings_post_uses_principal_client_id(attacker_client):
    """POST /settings binds the UPDATE to the authenticated client's client_id; a
    conflicting X-Tenant-ID cannot redirect the write to another client."""
    cap = _CapturingSession(principal=attacker_client)

    async def _override():
        yield cap
    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = dict(_client_headers(attacker_client))
            headers["X-Tenant-ID"] = str(VICTIM_TENANT_ID)  # conflicting on purpose
            resp = await ac.post(
                "/api/reports/email/settings",
                json={"enabled": True, "recipients": ["mine@test.invalid"], "frequency": "daily"},
                headers=headers,
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200, resp.text
    update_calls = [c for c in cap.calls if c[0].strip().startswith("update")]
    assert update_calls, "no UPDATE issued"
    bound = update_calls[-1][1]
    assert bound.get("cid") == str(attacker_client.client_id), (
        f"settings UPDATE used cid={bound.get('cid')} — expected principal "
        f"{attacker_client.client_id}; header tenant must NOT redirect the write"
    )
    assert str(VICTIM_TENANT_ID) not in bound.values()
    assert any(c[0] == "<commit>" for c in cap.calls), "write was not committed"
