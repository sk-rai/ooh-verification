"""Phase C — Real endpoint-level two-client tracking isolation tests (Task 9).

Spec: .kiro/specs/map-tracking-isolation-fix (Task 9, refinement 4)

These exercise GET /api/tracks/summary and GET /api/tracks/vendor/{vendor_id}
end-to-end (real httpx AsyncClient, real Postgres, real auth headers) with two
separately-authenticated clients A and B on the SAME tenant, covering every
branch of the date-bounded campaign rule with orphan fallback:

  entitled(C, V, D) = IN-WINDOW(C, V, D) OR
                      (NOT COVERED-BY-ANY-CLIENT(V, D) AND C == V.created_by_client_id)

Cases covered (see design Property 3):
  - IN-WINDOW: campaign-owning client sees it, the other does not.
  - POST-CAMPAIGN HAND-OFF: sequential campaigns each gate their own window.
  - ORPHAN (live-demo 9BIZMV shape): creator sees all orphan days, others none.
  - NO ASSIGNMENTS AT ALL: every day is orphan; only the creator sees them.
  - NONEXISTENT vendor: /vendor/{id} returns the empty shape, not 404.
  - CONFLICT/OVERLAP: both campaign owners see the day; a third client does not.
  - IN-WINDOW BEATS HOME-CLIENT: an in-window day suppresses the creator's orphan
    fallback for that day, even though the creator still owns the vendor.

Harness: dedicated NullPool engine + committed seeding with explicit teardown,
mirroring test_tracks_isolation.py / test_tracks_predicate_safety.py. Only rows
created by this module's seeder are ever written or deleted.
"""
import os
import uuid
from datetime import datetime, date, timezone

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("USE_MOCK_STORAGE", "true")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.client import Client, SubscriptionTier, SubscriptionStatus
from app.models.campaign import Campaign, CampaignType, CampaignStatus
from app.models.campaign_vendor_assignment import CampaignVendorAssignment
from app.models.vendor import Vendor, VendorStatus
from app.models.vendor_track import VendorTrack

from tests.hotfix_support import TEST_DATABASE_URL, DEFAULT_TENANT_ID, hotfix_runtime_env  # noqa: F401

_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
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
        self.client_ids: list = []
        self.campaign_ids: list = []
        self.vendor_ids: list = []
        self.assignment_ids: list = []
        self.track_ids: list = []

    async def client(self, s, tag):
        c = Client(
            client_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID,
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

    async def vendor(self, s, creator):
        v = Vendor(
            vendor_id=uuid.uuid4().hex[:6].upper(), tenant_id=DEFAULT_TENANT_ID,
            created_by_client_id=creator.client_id, name="Endpoint Test Vendor",
            phone_number="+919000000000", status=VendorStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(v)
        await s.flush()
        self.vendor_ids.append(v.vendor_id)
        return v

    async def campaign(self, s, owner, start, end):
        cam = Campaign(
            campaign_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID, client_id=owner.client_id,
            campaign_code=f"CAM-{uuid.uuid4().hex[:8].upper()}", name="Endpoint Test Campaign",
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
        return a

    async def track(self, s, vendor, day):
        t = VendorTrack(
            track_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID, vendor_id=vendor.vendor_id,
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
        return t

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
            await s.commit()


@pytest_asyncio.fixture
async def seeder() -> _Seeder:
    sd = _Seeder()
    yield sd
    await sd.cleanup()


def _headers(client: Client) -> dict:
    token = create_access_token(
        data={"sub": str(client.client_id), "type": "client", "email": client.email}
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(DEFAULT_TENANT_ID)}


async def _summary_dates_for(api_client, client, vendor_id, start="2026-10-01", end="2026-10-31"):
    resp = await api_client.get(
        f"/api/tracks/summary?start_date={start}&end_date={end}", headers=_headers(client)
    )
    assert resp.status_code == 200, resp.text
    return {r["date"] for r in resp.json()["rows"] if r["vendor_id"] == vendor_id}


async def _vendor_points(api_client, client, vendor_id, day: str):
    resp = await api_client.get(
        f"/api/tracks/vendor/{vendor_id}?date={day}", headers=_headers(client)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# IN-WINDOW
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_in_window_only_campaign_owner_sees_track(api_client, seeder):
    async with TestSessionLocal() as s:
        a = await seeder.client(s, "iwA")
        b = await seeder.client(s, "iwB")
        v = await seeder.vendor(s, a)
        cam = await seeder.campaign(
            s, a, datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 10, 10, tzinfo=timezone.utc)
        )
        await seeder.assign(s, cam, v)
        await seeder.track(s, v, date(2026, 10, 5))
        await s.commit()

    a_dates = await _summary_dates_for(api_client, a, v.vendor_id)
    b_dates = await _summary_dates_for(api_client, b, v.vendor_id)
    assert a_dates == {"2026-10-05"}
    assert b_dates == set()

    a_body = await _vendor_points(api_client, a, v.vendor_id, "2026-10-05")
    b_body = await _vendor_points(api_client, b, v.vendor_id, "2026-10-05")
    assert a_body["points"] and a_body["stats"] is not None
    assert b_body["points"] == [] and b_body["stats"] is None


# --------------------------------------------------------------------------- #
# POST-CAMPAIGN HAND-OFF
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_campaign_handoff_each_client_sees_only_its_own_window(api_client, seeder):
    async with TestSessionLocal() as s:
        a = await seeder.client(s, "hoA")
        b = await seeder.client(s, "hoB")
        v = await seeder.vendor(s, a)
        cam_a = await seeder.campaign(
            s, a, datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 10, 5, tzinfo=timezone.utc)
        )
        cam_b = await seeder.campaign(
            s, b, datetime(2026, 10, 6, tzinfo=timezone.utc), datetime(2026, 10, 10, tzinfo=timezone.utc)
        )
        await seeder.assign(s, cam_a, v)
        await seeder.assign(s, cam_b, v)
        await seeder.track(s, v, date(2026, 10, 3))   # D1 -> A's window
        await seeder.track(s, v, date(2026, 10, 8))   # D2 -> B's window
        await s.commit()

    a_dates = await _summary_dates_for(api_client, a, v.vendor_id)
    b_dates = await _summary_dates_for(api_client, b, v.vendor_id)
    assert a_dates == {"2026-10-03"}
    assert b_dates == {"2026-10-08"}


# --------------------------------------------------------------------------- #
# ORPHAN (live-demo 9BIZMV shape)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_orphan_days_live_demo_shape_creator_only(api_client, seeder):
    async with TestSessionLocal() as s:
        a = await seeder.client(s, "orphA")
        b = await seeder.client(s, "orphB")
        v = await seeder.vendor(s, a)
        cam = await seeder.campaign(
            s, a, datetime(2026, 3, 1, tzinfo=timezone.utc), datetime(2026, 5, 31, tzinfo=timezone.utc)
        )
        await seeder.assign(s, cam, v)
        orphan_days = [date(2026, 10, d) for d in range(5, 11)]
        for d in orphan_days:
            await seeder.track(s, v, d)
        await s.commit()

    a_dates = await _summary_dates_for(api_client, a, v.vendor_id)
    b_dates = await _summary_dates_for(api_client, b, v.vendor_id)
    assert a_dates == {d.isoformat() for d in orphan_days}
    assert b_dates == set()


# --------------------------------------------------------------------------- #
# NO ASSIGNMENTS AT ALL
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_no_assignments_at_all_every_day_is_orphan(api_client, seeder):
    async with TestSessionLocal() as s:
        a = await seeder.client(s, "naaA")
        b = await seeder.client(s, "naaB")
        v = await seeder.vendor(s, a)
        for d in (date(2026, 10, 1), date(2026, 10, 2)):
            await seeder.track(s, v, d)
        await s.commit()

    a_dates = await _summary_dates_for(api_client, a, v.vendor_id)
    b_dates = await _summary_dates_for(api_client, b, v.vendor_id)
    assert a_dates == {"2026-10-01", "2026-10-02"}
    assert b_dates == set()


# --------------------------------------------------------------------------- #
# NONEXISTENT vendor
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_nonexistent_vendor_returns_empty_shape_not_404(api_client, seeder):
    async with TestSessionLocal() as s:
        a = await seeder.client(s, "nxA")
        await s.commit()

    fake_vendor_id = uuid.uuid4().hex[:6].upper()
    body = await _vendor_points(api_client, a, fake_vendor_id, "2026-10-05")
    assert body == {
        "vendor_id": fake_vendor_id, "date": "2026-10-05", "points": [], "stats": None
    }


# --------------------------------------------------------------------------- #
# CONFLICT / OVERLAP
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_overlapping_campaigns_both_owners_see_it_third_client_does_not(api_client, seeder):
    async with TestSessionLocal() as s:
        a = await seeder.client(s, "ovA")
        b = await seeder.client(s, "ovB")
        c = await seeder.client(s, "ovC")  # creator, no covering campaign of its own
        v = await seeder.vendor(s, c)
        for owner in (a, b):
            cam = await seeder.campaign(
                s, owner, datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 10, 31, tzinfo=timezone.utc)
            )
            await seeder.assign(s, cam, v)
        await seeder.track(s, v, date(2026, 10, 5))
        await s.commit()

    a_dates = await _summary_dates_for(api_client, a, v.vendor_id)
    b_dates = await _summary_dates_for(api_client, b, v.vendor_id)
    c_dates = await _summary_dates_for(api_client, c, v.vendor_id)
    assert a_dates == {"2026-10-05"}
    assert b_dates == {"2026-10-05"}
    assert c_dates == set(), "creator with no covering campaign must not see an in-window day"


# --------------------------------------------------------------------------- #
# IN-WINDOW BEATS HOME-CLIENT
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_in_window_suppresses_home_client_orphan_fallback(api_client, seeder):
    """Vendor V is created by B, but day D falls inside A's covering campaign
    window. Only A sees D; B's orphan fallback is suppressed for that day because
    D is covered by A's campaign."""
    async with TestSessionLocal() as s:
        a = await seeder.client(s, "iwbA")
        b = await seeder.client(s, "iwbB")
        v = await seeder.vendor(s, b)  # created_by B
        cam = await seeder.campaign(
            s, a, datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 10, 10, tzinfo=timezone.utc)
        )
        await seeder.assign(s, cam, v)
        await seeder.track(s, v, date(2026, 10, 5))
        await s.commit()

    a_dates = await _summary_dates_for(api_client, a, v.vendor_id)
    b_dates = await _summary_dates_for(api_client, b, v.vendor_id)
    assert a_dates == {"2026-10-05"}
    assert b_dates == set(), "creator B must not see an in-window day covered by A's campaign"


# --------------------------------------------------------------------------- #
# CROSS-TENANT / X-Tenant-ID header (security follow-up characterization)
# --------------------------------------------------------------------------- #
OTHER_TENANT_ID = uuid.UUID("11111111-2222-4333-8444-555555555555")


@pytest.mark.asyncio
async def test_spoofed_tenant_header_cannot_read_foreign_tenant_tracks(api_client, seeder):
    """A client of tenant T2 presenting T1's X-Tenant-ID must not read T1 tracks.

    Records the OBSERVED status codes explicitly (not an either/or): see the
    printed OBSERVED line and the exact assertions below. Context for the separate
    security follow-up: TenantContextMiddleware trusts a client-supplied
    X-Tenant-ID if that tenant is active, and get_current_client resolves identity
    from the JWT only. The hotfix does not change this; this test pins that the
    entitlement predicate still yields no foreign data.
    """
    from app.models.tenant_config import TenantConfig

    async with TestSessionLocal() as s:
        s.add(TenantConfig(
            tenant_id=OTHER_TENANT_ID, tenant_name="Other Tenant",
            subdomain=f"other-{uuid.uuid4().hex[:8]}", is_active=True,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        ))
        await s.flush()
        a = await seeder.client(s, "xtA")  # T1 creator
        z = Client(
            client_id=uuid.uuid4(), tenant_id=OTHER_TENANT_ID,
            email=f"xtZ_{uuid.uuid4().hex[:8]}@x.com", password_hash="x",
            company_name="Client xtZ", phone_number="+10000000000",
            subscription_tier=SubscriptionTier.FREE,
            subscription_status=SubscriptionStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(z)
        await s.flush()
        seeder.client_ids.append(z.client_id)
        v = await seeder.vendor(s, a)
        await seeder.track(s, v, date(2026, 10, 5))
        await s.commit()

    try:
        # Z (T2) spoofs T1's header.
        spoof_headers = _headers(z)  # X-Tenant-ID = T1 (DEFAULT_TENANT_ID)
        summary = await api_client.get(
            "/api/tracks/summary?start_date=2026-10-01&end_date=2026-10-31", headers=spoof_headers
        )
        vendor = await api_client.get(
            f"/api/tracks/vendor/{v.vendor_id}?date=2026-10-05", headers=spoof_headers
        )
        print(f"OBSERVED spoofed-header status: summary={summary.status_code} vendor={vendor.status_code}")

        assert summary.status_code == 200, summary.text
        assert [r for r in summary.json()["rows"] if r["vendor_id"] == v.vendor_id] == []
        assert vendor.status_code == 200, vendor.text
        assert vendor.json()["points"] == [] and vendor.json()["stats"] is None
    finally:
        async with TestSessionLocal() as s:
            await s.execute(delete(Client).where(Client.client_id == z.client_id))
            from app.models.tenant_config import TenantConfig as _TC
            await s.execute(delete(_TC).where(_TC.tenant_id == OTHER_TENANT_ID))
            await s.commit()
        seeder.client_ids.remove(z.client_id)
