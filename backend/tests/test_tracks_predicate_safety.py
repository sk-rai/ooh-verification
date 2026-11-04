"""Phase B safety tests for the tracking entitlement predicates (tracks.py).

Spec: .kiro/specs/map-tracking-isolation-fix  (Phase B, Task 5; owner-mandated)

Covers three safety properties that the Phase A tests do not:

  1. UTC vs non-UTC DATABASE SESSIONS
     Campaign bounds are timestamptz at midnight UTC; vendor_tracks.track_date is a
     DATE. The predicates must convert the bounds to a date explicitly in UTC
     (timezone('UTC', ts)::date). If they relied on the session TimeZone, a session
     west of UTC would shift a 00:00Z bound to the previous day and silently change
     which days are in-window. These tests run the SAME scenario under UTC, a
     negative-offset zone (America/Los_Angeles) and a positive-offset zone
     (Asia/Kolkata) and require identical results. Inclusive start AND end are
     asserted.

  2. CROSS-TENANT ASSIGNMENT COLLISIONS
     campaign_vendor_assignments has NO tenant_id, so tenant safety must come from
     the joined Campaign and Vendor. A covering campaign belonging to ANOTHER tenant
     (linked to the vendor through a stray assignment row) must neither grant
     entitlement nor suppress the creator's orphan fallback.

  3. ORPHAN FALLBACK TENANT ISOLATION
     The creating-client check must resolve the vendor in the SAME tenant as the
     candidate VendorTrack. A track row whose tenant differs from its vendor's tenant
     must not be visible to the vendor's creator.

Entitlement rule under test (owner-confirmed): in-window campaign ownership grants
visibility; if no client has a covering campaign only the creating client sees the
orphan day; overlapping covering campaigns grant visibility to both owners; an
in-window assignment suppresses the home-client orphan fallback.

Harness: own NullPool engine and committed seeding with unique ids and explicit
teardown (same isolation approach as the other hotfix tests; conftest untouched).
Predicate-level tests query the real DB with the real predicate, so tenant
correlation is verified independently of the HTTP auth layer.
"""
import os
import uuid
from datetime import datetime, date, timezone

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("USE_MOCK_STORAGE", "true")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.api.tracks import _visible_to
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.campaign import Campaign, CampaignType, CampaignStatus
from app.models.campaign_vendor_assignment import CampaignVendorAssignment
from app.models.client import Client, SubscriptionTier, SubscriptionStatus
from app.models.tenant_config import TenantConfig
from app.models.vendor import Vendor, VendorStatus
from app.models.vendor_track import VendorTrack

from tests.hotfix_support import TEST_DATABASE_URL, DEFAULT_TENANT_ID, hotfix_runtime_env  # noqa: F401

_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

OTHER_TENANT_ID = uuid.UUID("11111111-2222-4333-8444-555555555555")


def _tz_engine(tz: str):
    """Engine whose every DB session runs with the given PostgreSQL TimeZone."""
    return create_async_engine(
        TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool,
        connect_args={"server_settings": {"timezone": tz}},
    )


class _Seeder:
    def __init__(self):
        self.tenant_ids: list = []
        self.client_ids: list = []
        self.campaign_ids: list = []
        self.vendor_ids: list = []
        self.assignment_ids: list = []
        self.track_ids: list = []

    async def other_tenant(self, s):
        s.add(TenantConfig(
            tenant_id=OTHER_TENANT_ID, tenant_name="Other Tenant",
            subdomain=f"other-{uuid.uuid4().hex[:8]}", is_active=True,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        ))
        await s.flush()
        self.tenant_ids.append(OTHER_TENANT_ID)

    async def client(self, s, tag, tenant_id=DEFAULT_TENANT_ID):
        c = Client(
            client_id=uuid.uuid4(), tenant_id=tenant_id,
            email=f"{tag}_{uuid.uuid4().hex[:8]}@x.com", password_hash="x",
            company_name=f"Client {tag}", phone_number="+10000000000",
            subscription_tier=SubscriptionTier.FREE,
            subscription_status=SubscriptionStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(c)
        await s.flush()
        self.client_ids.append(c.client_id)
        return c

    async def vendor(self, s, creator, tenant_id=DEFAULT_TENANT_ID):
        v = Vendor(
            vendor_id=uuid.uuid4().hex[:6].upper(), tenant_id=tenant_id,
            created_by_client_id=creator.client_id, name="Freelancer",
            phone_number="+919000000000", status=VendorStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(v)
        await s.flush()
        self.vendor_ids.append(v.vendor_id)
        return v

    async def campaign(self, s, owner, start, end, tenant_id=DEFAULT_TENANT_ID):
        cam = Campaign(
            campaign_id=uuid.uuid4(), tenant_id=tenant_id, client_id=owner.client_id,
            campaign_code=f"CAM-{uuid.uuid4().hex[:8].upper()}", name="Safety Campaign",
            campaign_type=CampaignType.OOH_ADVERTISING, start_date=start, end_date=end,
            status=CampaignStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(cam)
        await s.flush()
        self.campaign_ids.append(cam.campaign_id)
        return cam

    async def assign(self, s, campaign, vendor):
        a = CampaignVendorAssignment(
            assignment_id=uuid.uuid4(), campaign_id=campaign.campaign_id,
            vendor_id=vendor.vendor_id,
            assigned_at=datetime.now(tz=timezone.utc),
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(a)
        await s.flush()
        self.assignment_ids.append(a.assignment_id)

    async def track(self, s, vendor, day, tenant_id=DEFAULT_TENANT_ID):
        t = VendorTrack(
            track_id=uuid.uuid4(), tenant_id=tenant_id, vendor_id=vendor.vendor_id,
            track_date=day,
            points=[{"lat": 19.07, "lon": 72.87, "timestamp_ms": 1000}],
            point_count=1, total_distance_meters=10.0, duration_seconds=60.0,
            status="completed",
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(t)
        await s.flush()
        self.track_ids.append(t.track_id)

    async def cleanup(self):
        async with TestSessionLocal() as s:
            if self.track_ids:
                await s.execute(delete(VendorTrack).where(VendorTrack.track_id.in_(self.track_ids)))
            if self.assignment_ids:
                await s.execute(delete(CampaignVendorAssignment).where(
                    CampaignVendorAssignment.assignment_id.in_(self.assignment_ids)))
            if self.campaign_ids:
                await s.execute(delete(Campaign).where(Campaign.campaign_id.in_(self.campaign_ids)))
            if self.vendor_ids:
                await s.execute(delete(Vendor).where(Vendor.vendor_id.in_(self.vendor_ids)))
            if self.client_ids:
                await s.execute(delete(Client).where(Client.client_id.in_(self.client_ids)))
            if self.tenant_ids:
                await s.execute(delete(TenantConfig).where(TenantConfig.tenant_id.in_(self.tenant_ids)))
            await s.commit()


@pytest_asyncio.fixture
async def seeder() -> _Seeder:
    sd = _Seeder()
    yield sd
    await sd.cleanup()


def _headers(client: Client, tenant_id=DEFAULT_TENANT_ID) -> dict:
    token = create_access_token(
        data={"sub": str(client.client_id), "type": "client", "email": client.email}
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant_id)}


async def _visible_days(client_id, tenant_id, vendor_id) -> set:
    """Run the REAL predicate against the DB (no HTTP/auth layer involved)."""
    async with TestSessionLocal() as s:
        rows = (await s.execute(
            select(VendorTrack.track_date).where(
                VendorTrack.tenant_id == tenant_id,
                VendorTrack.vendor_id == vendor_id,
                _visible_to(client_id),
            )
        )).scalars().all()
    return set(rows)


# --------------------------------------------------------------------------- #
# 1. UTC vs non-UTC database sessions
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
@pytest.mark.parametrize("session_tz", ["UTC", "America/Los_Angeles", "Asia/Kolkata"])
async def test_window_boundaries_independent_of_db_session_timezone(seeder, session_tz):
    """Inclusive UTC boundaries hold under any PostgreSQL session TimeZone.

    A's campaign covers [2026-10-05T00:00Z, 2026-10-07T00:00Z]. V was created by B.
    Tracks exist on Oct 4, 5, 6, 7, 8. Expected (UTC, inclusive both ends):
      A (campaign owner)  -> Oct 5, 6, 7   (in-window)
      B (creating client) -> Oct 4, 8      (orphan days; in-window days suppress B)
    Under a naive ::date cast in America/Los_Angeles the start bound would become
    Oct 4 and the end bound Oct 6, flipping Oct 4 and Oct 7. All sessions must
    yield the identical result.
    """
    async with TestSessionLocal() as s:
        a = await seeder.client(s, "winA")
        b = await seeder.client(s, "winB")
        v = await seeder.vendor(s, b)  # created by B
        cam = await seeder.campaign(
            s, a,
            datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 7, 0, 0, tzinfo=timezone.utc),
        )
        await seeder.assign(s, cam, v)
        for d in (4, 5, 6, 7, 8):
            await seeder.track(s, v, date(2026, 10, d))
        await s.commit()

    # Prove the session really runs in the requested zone (guards against a no-op test).
    tz_engine = _tz_engine(session_tz)
    tz_sessions = async_sessionmaker(tz_engine, class_=AsyncSession, expire_on_commit=False)
    async with tz_sessions() as probe:
        shown = (await probe.execute(text("SHOW TimeZone"))).scalar()
    assert shown == session_tz, f"session tz not applied: wanted {session_tz}, got {shown}"

    # Predicate-level check under that session timezone.
    async with tz_sessions() as s:
        def days_for(client_id):
            return select(VendorTrack.track_date).where(
                VendorTrack.tenant_id == DEFAULT_TENANT_ID,
                VendorTrack.vendor_id == v.vendor_id,
                _visible_to(client_id),
            )
        a_days = set((await s.execute(days_for(a.client_id))).scalars().all())
        b_days = set((await s.execute(days_for(b.client_id))).scalars().all())

    assert a_days == {date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7)}, (
        f"[{session_tz}] campaign owner window wrong: {sorted(a_days)}"
    )
    assert b_days == {date(2026, 10, 4), date(2026, 10, 8)}, (
        f"[{session_tz}] creator orphan days wrong: {sorted(b_days)}"
    )

    # Endpoint-level check with the endpoint's own DB session in that timezone.
    async def override_get_db():
        async with tz_sessions() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ra = await ac.get("/api/tracks/summary?start_date=2026-10-01&end_date=2026-10-31",
                              headers=_headers(a))
            rb = await ac.get("/api/tracks/summary?start_date=2026-10-01&end_date=2026-10-31",
                              headers=_headers(b))
    finally:
        app.dependency_overrides.pop(get_db, None)
        await tz_engine.dispose()

    assert ra.status_code == 200, ra.text
    assert rb.status_code == 200, rb.text
    ep_a = {r["date"] for r in ra.json()["rows"] if r["vendor_id"] == v.vendor_id}
    ep_b = {r["date"] for r in rb.json()["rows"] if r["vendor_id"] == v.vendor_id}
    assert ep_a == {"2026-10-05", "2026-10-06", "2026-10-07"}, f"[{session_tz}] {sorted(ep_a)}"
    assert ep_b == {"2026-10-04", "2026-10-08"}, f"[{session_tz}] {sorted(ep_b)}"


# --------------------------------------------------------------------------- #
# 2. Cross-tenant assignment collisions
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_other_tenant_campaign_grants_no_entitlement(seeder):
    """A covering campaign from ANOTHER tenant, linked to our vendor through a stray
    assignment row (the assignment table has no tenant_id), must NOT make its owner
    entitled to our tenant's track days.
    """
    async with TestSessionLocal() as s:
        await seeder.other_tenant(s)
        a = await seeder.client(s, "ctA")                                  # tenant T1
        z = await seeder.client(s, "ctZ", tenant_id=OTHER_TENANT_ID)       # tenant T2
        v = await seeder.vendor(s, a)                                      # T1 vendor, created by A
        foreign = await seeder.campaign(
            s, z,
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            datetime(2026, 10, 31, tzinfo=timezone.utc),
            tenant_id=OTHER_TENANT_ID,
        )
        await seeder.assign(s, foreign, v)  # stray cross-tenant assignment
        for d in (5, 6, 7):
            await seeder.track(s, v, date(2026, 10, d))  # T1 tracks
        await s.commit()

    # Z (even if it could present T1) is not entitled: its campaign is in T2.
    assert await _visible_days(z.client_id, DEFAULT_TENANT_ID, v.vendor_id) == set()


@pytest.mark.asyncio
async def test_other_tenant_campaign_does_not_suppress_creator_orphan_fallback(seeder):
    """The same stray cross-tenant coverage must not count as 'covered by some
    client' for T1's track days, so the creator A keeps its orphan-day access.
    """
    async with TestSessionLocal() as s:
        await seeder.other_tenant(s)
        a = await seeder.client(s, "supA")
        z = await seeder.client(s, "supZ", tenant_id=OTHER_TENANT_ID)
        v = await seeder.vendor(s, a)
        foreign = await seeder.campaign(
            s, z,
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            datetime(2026, 10, 31, tzinfo=timezone.utc),
            tenant_id=OTHER_TENANT_ID,
        )
        await seeder.assign(s, foreign, v)
        for d in (5, 6, 7):
            await seeder.track(s, v, date(2026, 10, d))
        await s.commit()

    assert await _visible_days(a.client_id, DEFAULT_TENANT_ID, v.vendor_id) == {
        date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7)
    }


@pytest.mark.asyncio
async def test_vendor_in_other_tenant_assignment_grants_no_entitlement(seeder):
    """The assignment must also resolve to a vendor in the track's tenant: client A
    (T1) owns a covering T1 campaign assigned to a vendor that lives in T2. A
    T1-tenant track row for that vendor (corrupt/colliding data) must not make A
    entitled, because the vendor's tenant (T2) differs from the track's (T1).
    """
    async with TestSessionLocal() as s:
        await seeder.other_tenant(s)
        a = await seeder.client(s, "vtA")                                   # T1
        z = await seeder.client(s, "vtZ", tenant_id=OTHER_TENANT_ID)        # T2
        v = await seeder.vendor(s, z, tenant_id=OTHER_TENANT_ID)            # vendor in T2
        cam = await seeder.campaign(
            s, a,
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            datetime(2026, 10, 31, tzinfo=timezone.utc),
        )                                                                    # T1 campaign
        await seeder.assign(s, cam, v)
        await seeder.track(s, v, date(2026, 10, 5), tenant_id=DEFAULT_TENANT_ID)  # T1 track row
        await s.commit()

    assert await _visible_days(a.client_id, DEFAULT_TENANT_ID, v.vendor_id) == set()


@pytest.mark.asyncio
async def test_cross_tenant_spoofed_header_sees_no_foreign_tracks(seeder):
    """Endpoint-level: a T2 client presenting T1's tenant header must not read T1's
    vendor tracks (defense in depth on top of the predicate tests above).
    """
    async def override_get_db():
        async with TestSessionLocal() as s:
            yield s

    async with TestSessionLocal() as s:
        await seeder.other_tenant(s)
        a = await seeder.client(s, "spA")
        z = await seeder.client(s, "spZ", tenant_id=OTHER_TENANT_ID)
        v = await seeder.vendor(s, a)
        foreign = await seeder.campaign(
            s, z,
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            datetime(2026, 10, 31, tzinfo=timezone.utc),
            tenant_id=OTHER_TENANT_ID,
        )
        await seeder.assign(s, foreign, v)
        await seeder.track(s, v, date(2026, 10, 5))
        await s.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/tracks/summary?start_date=2026-10-01&end_date=2026-10-31",
                headers=_headers(z, tenant_id=DEFAULT_TENANT_ID),
            )
            vresp = await ac.get(
                f"/api/tracks/vendor/{v.vendor_id}?date=2026-10-05",
                headers=_headers(z, tenant_id=DEFAULT_TENANT_ID),
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    # Either the auth layer rejects the mismatch or the predicate returns nothing;
    # in no case may T1's vendor track be visible.
    if resp.status_code == 200:
        assert [r for r in resp.json()["rows"] if r["vendor_id"] == v.vendor_id] == []
    else:
        assert resp.status_code in (401, 403, 404)
    if vresp.status_code == 200:
        body = vresp.json()
        assert body.get("points") == [] and body.get("stats") is None
    else:
        assert vresp.status_code in (401, 403, 404)


# --------------------------------------------------------------------------- #
# 3. Orphan fallback tenant isolation
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_orphan_fallback_resolves_vendor_in_same_tenant_only(seeder):
    """A track row whose tenant (T2) differs from its vendor's tenant (T1) must not
    be visible to the vendor's creator via the orphan fallback: the creating-client
    check resolves the vendor within the CANDIDATE TRACK's tenant.
    """
    async with TestSessionLocal() as s:
        await seeder.other_tenant(s)
        a = await seeder.client(s, "orA")                        # T1 creator
        v = await seeder.vendor(s, a)                            # vendor lives in T1
        await seeder.track(s, v, date(2026, 10, 5), tenant_id=OTHER_TENANT_ID)  # mismatched track tenant
        await s.commit()

    # Query the T2 track rows: creator A (vendor in T1) is NOT entitled in T2.
    assert await _visible_days(a.client_id, OTHER_TENANT_ID, v.vendor_id) == set()


@pytest.mark.asyncio
async def test_orphan_fallback_still_works_within_same_tenant(seeder):
    """Control for the test above: with matching tenants the creator IS entitled
    to orphan days (so the isolation test cannot pass vacuously).
    """
    async with TestSessionLocal() as s:
        a = await seeder.client(s, "ctlA")
        v = await seeder.vendor(s, a)
        await seeder.track(s, v, date(2026, 10, 5))
        await s.commit()

    assert await _visible_days(a.client_id, DEFAULT_TENANT_ID, v.vendor_id) == {date(2026, 10, 5)}


@pytest.mark.asyncio
async def test_overlap_grants_both_owners_and_suppresses_home_client(seeder):
    """Approved overlap behavior: when two clients both hold covering campaigns for
    the same vendor/day, BOTH are entitled via their own campaign, and the vendor's
    creator (a third client with no covering campaign) is suppressed on that day.
    No assignment constraint is introduced; this documents the accepted tradeoff.
    """
    async with TestSessionLocal() as s:
        a = await seeder.client(s, "ovA")
        b = await seeder.client(s, "ovB")
        c = await seeder.client(s, "ovC")        # creator, no covering campaign
        v = await seeder.vendor(s, c)
        for owner in (a, b):
            cam = await seeder.campaign(
                s, owner,
                datetime(2026, 10, 1, tzinfo=timezone.utc),
                datetime(2026, 10, 31, tzinfo=timezone.utc),
            )
            await seeder.assign(s, cam, v)
        await seeder.track(s, v, date(2026, 10, 5))
        await s.commit()

    day = {date(2026, 10, 5)}
    assert await _visible_days(a.client_id, DEFAULT_TENANT_ID, v.vendor_id) == day
    assert await _visible_days(b.client_id, DEFAULT_TENANT_ID, v.vendor_id) == day
    assert await _visible_days(c.client_id, DEFAULT_TENANT_ID, v.vendor_id) == set()
