"""Phase A characterization + preservation tests for the GPS tracking bug (Bug 2).

Spec: .kiro/specs/map-tracking-isolation-fix  (Tasks 2 & 3, tracks portion)

Bug 2 (design Property 3 / isBugCondition_Tracks): GET /api/tracks/summary and
GET /api/tracks/vendor/{id} scope reads by VendorTrack.tenant_id only. On the
single shared tenant every client sees every other client's tracks.

Authoritative entitlement rule (owner-confirmed, date-bounded campaign scope with
orphan fallback): a track (vendor V, date D) is visible to client C iff
  (in-window) C owns a campaign assigned to V whose [start_date, end_date]
              covers D; OR
  (orphan)    no client has such a covering campaign AND C == V.created_by_client_id.

Tests in this module and what they map to:
  - test_orphan_days_not_leaked_to_other_client
        Task 2 / Property 3 (Bug Condition). EXPECTED-FAIL pre-fix (xfail,
        strict=False): B currently sees A's vendor's orphan-day tracks via
        /summary; flips to xpass after Phase B.
  - test_vendor_endpoint_no_existence_leak
        Task 2 / Property 3 (Bug Condition). EXPECTED-FAIL pre-fix (xfail):
        /vendor/{V} as B returns A's real track instead of the empty shape.
  - test_creating_client_sees_orphan_days
        Task 3 / Property 4 (Preservation). EXPECTED-PASS baseline: the creating
        client A sees all of V's orphan days (orphan fallback keeps them for the
        creator). Green now; must stay green after the fix.
  - test_summary_shape_and_ordering_baseline
        Task 3 / Property 4 (Preservation). EXPECTED-PASS baseline: characterize
        /summary response shape + track_date DESC ordering so Phase B can't regress it.
  - test_vendor_endpoint_self_shape_baseline
        Task 3 / Property 4 (Preservation). EXPECTED-PASS baseline: /vendor/{V}
        for the entitled creating client returns the populated shape + stats.
  - test_sync_and_me_write_self_read_untouched
        Task 3 / Property 4 (Preservation). EXPECTED-PASS baseline: POST /sync
        (vendor-authed write) and GET /me (vendor self-read) behave as today.

Harness notes (OF-3 lesson): the tenant middleware and endpoint run on the
app-runtime session, so endpoint-visible data is seeded through a COMMITTED
session (TestSessionLocal) with UNIQUE ids and deleted in teardown. ``api_client``
overrides get_db with a fresh committed session per call. Clients A and B share
the SAME tenant on purpose. Tests create + clean up only their OWN rows; no
real/demo track rows are deleted.

ENTITLEMENT-RULE NOTE: the date-bounded campaign rule with orphan fallback
supersedes BOTH the earlier ``created_by_client_id``-only scoping approach and the
interim active-``VendorClientAssociation`` approach. ``created_by_client_id`` is
used ONLY for the orphan fallback (days no client's campaign covers). The
in-window / orphan / conflict branches of /summary are exercised directly by
test_summary_in_window_branch, test_creating_client_sees_orphan_days (orphan) and
test_summary_conflict_overlap_branch below.

POST-FIX NOTE: the Bug 1 / Bug 2 tests below were xfail(strict=False) while the bugs existed (Phase A). Phase B fixed both, so the markers were removed; they are now plain regression guards and will FAIL (not xfail) if either bug returns.
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

# Dedicated NullPool engine for this module (see test_map_locations_isolation.py
# for rationale): a fresh asyncpg connection per checkout avoids the
# "another operation is in progress" contention when the per-test seed session
# and the endpoint/middleware sessions are live on the same event loop.
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
    """Commits seed rows to the test DB and records ids for teardown."""

    def __init__(self):
        self.client_ids: list = []
        self.campaign_ids: list = []
        self.vendor_ids: list = []
        self.assignment_ids: list = []
        self.track_ids: list = []

    async def client(self, s, email, company):
        c = Client(
            client_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID, email=email,
            password_hash="x", company_name=company, phone_number="+10000000000",
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
            vendor_id=f"{uuid.uuid4().hex[:6].upper()}", tenant_id=DEFAULT_TENANT_ID,
            created_by_client_id=creator.client_id, name="Freelancer",
            phone_number="+919000000000", status=VendorStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(v)
        await s.flush()
        self.vendor_ids.append(v.vendor_id)
        return v

    async def campaign(self, s, client, start, end):
        cam = Campaign(
            campaign_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID,
            client_id=client.client_id,
            campaign_code=f"CAM-{uuid.uuid4().hex[:8].upper()}", name="Trk Campaign",
            campaign_type=CampaignType.OOH_ADVERTISING,
            start_date=start, end_date=end, status=CampaignStatus.ACTIVE,
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

    async def track(self, s, vendor, track_date):
        t = VendorTrack(
            track_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID,
            vendor_id=vendor.vendor_id, track_date=track_date,
            points=[{"lat": 19.07, "lon": 72.87, "timestamp_ms": 1000},
                    {"lat": 19.08, "lon": 72.88, "timestamp_ms": 2000}],
            point_count=2, total_distance_meters=1234.0,
            start_time=datetime(track_date.year, track_date.month, track_date.day, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(track_date.year, track_date.month, track_date.day, 17, 0, tzinfo=timezone.utc),
            duration_seconds=28800.0, status="completed",
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


def _client_headers(client: Client) -> dict:
    token = create_access_token(
        data={"sub": str(client.client_id), "type": "client", "email": client.email}
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(DEFAULT_TENANT_ID)}


def _vendor_headers(vendor: Vendor, client: Client) -> dict:
    token = create_access_token(
        data={"sub": str(client.client_id), "type": "vendor", "vendor_id": vendor.vendor_id}
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(DEFAULT_TENANT_ID)}


# 9BIZMV-style scenario: creator A, orphan Oct days, assignments only Mar 2026.
async def _seed_orphan_scenario(seeder: _Seeder):
    """Returns (client_a, client_b, vendor_v, [orphan_days]).

    V is created by A. A's only campaign assignment for V is in March 2026, which
    does NOT cover the October track days, so all 6 Oct days are orphan days whose
    only entitled client is the creator A. B has no covering campaign and did not
    create V, so B is not entitled to any of them.
    """
    async with TestSessionLocal() as s:
        a = await seeder.client(s, f"a_{uuid.uuid4().hex[:8]}@x.com", "Creator A (Lynksavvy-style)")
        b = await seeder.client(s, f"b_{uuid.uuid4().hex[:8]}@x.com", "Other B (Corrxperts-style)")
        v = await seeder.vendor(s, a)  # created_by A
        cam_a = await seeder.campaign(
            s, a,
            datetime(2026, 3, 1, tzinfo=timezone.utc),
            datetime(2026, 3, 31, tzinfo=timezone.utc),
        )
        await seeder.assign(s, cam_a, v)
        track_days = [date(2026, 10, d) for d in range(5, 11)]  # Oct 5..10 (orphan)
        for d in track_days:
            await seeder.track(s, v, d)
        await s.commit()
    return a, b, v, track_days


# --------------------------------------------------------------------------- #
# Task 2 — bug characterization (EXPECTED-FAIL pre-fix -> xpass post-fix)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_orphan_days_not_leaked_to_other_client(api_client, seeder):
    """Task 2 / Property 3 (Bug Condition) — EXPECTED-FAIL pre-fix.

    Vendor V's October days are orphan days (no covering campaign). Client B (no
    covering campaign, did not create V) must see NONE of them via /summary. The
    unfixed endpoint scopes by tenant only, so B sees them — the leak that proves
    the bug.
    """
    a, b, v, days = await _seed_orphan_scenario(seeder)

    resp = await api_client.get(
        "/api/tracks/summary?start_date=2026-10-01&end_date=2026-10-31",
        headers=_client_headers(b),
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json().get("rows", [])
    leaked = [r for r in rows if r["vendor_id"] == v.vendor_id]

    # EXPECTED POST-FIX: B sees none of V's orphan days.
    assert leaked == [], (
        f"cross-client leak: B saw {len(leaked)} of A-vendor {v.vendor_id}'s "
        f"orphan days on {[r['date'] for r in leaked]}"
    )


@pytest.mark.asyncio
async def test_vendor_endpoint_no_existence_leak(api_client, seeder):
    """Task 2 / Property 3 (Bug Condition) — EXPECTED-FAIL pre-fix.

    /vendor/{V}?date=D for a vendor B is not entitled to must return the standard
    empty shape {vendor_id, date, points: [], stats: None} (no existence leak).
    The unfixed endpoint returns A's real track.
    """
    a, b, v, days = await _seed_orphan_scenario(seeder)

    resp = await api_client.get(
        f"/api/tracks/vendor/{v.vendor_id}?date=2026-10-05",
        headers=_client_headers(b),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # EXPECTED POST-FIX: empty shape, no points, no stats.
    assert body.get("points") == [], (
        f"existence/data leak: B received points for A-vendor {v.vendor_id}"
    )
    assert body.get("stats") is None


# --------------------------------------------------------------------------- #
# Task 3 (tracks) — preservation baselines (EXPECTED-PASS now and after fix)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_creating_client_sees_orphan_days(api_client, seeder):
    """Task 3 / Property 4 (Preservation) — EXPECTED-PASS baseline.

    The creating client A sees all of V's orphan days (mirrors 'Lynksavvy still
    sees the 6 demo orphan days'). Green now (tenant matches) and must stay green
    after the fix (A is entitled via the orphan fallback).
    """
    a, b, v, days = await _seed_orphan_scenario(seeder)

    resp = await api_client.get(
        "/api/tracks/summary?start_date=2026-10-01&end_date=2026-10-31",
        headers=_client_headers(a),
    )
    assert resp.status_code == 200, resp.text
    rows = [r for r in resp.json().get("rows", []) if r["vendor_id"] == v.vendor_id]
    assert len(rows) == len(days), (
        f"creating client should see all {len(days)} orphan days, saw {len(rows)}"
    )


@pytest.mark.asyncio
async def test_summary_shape_and_ordering_baseline(api_client, seeder):
    """Task 3 / Property 4 (Preservation) — EXPECTED-PASS baseline.

    Characterize the current /summary response shape and the track_date DESC
    ordering for the entitled creating client, so Phase B cannot regress them.
    """
    a, b, v, days = await _seed_orphan_scenario(seeder)

    resp = await api_client.get(
        "/api/tracks/summary?start_date=2026-10-01&end_date=2026-10-31",
        headers=_client_headers(a),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Top-level shape.
    assert set(body.keys()) >= {"period", "total_vendors", "total_tracks", "rows"}
    assert body["period"] == {"start": "2026-10-01", "end": "2026-10-31"}

    v_rows = [r for r in body["rows"] if r["vendor_id"] == v.vendor_id]
    assert len(v_rows) == len(days)

    # Per-row shape.
    for r in v_rows:
        for key in ("date", "vendor_id", "vendor_name", "vendor_phone",
                    "point_count", "distance_km", "start_time", "end_time",
                    "duration_hours", "status"):
            assert key in r, f"summary row missing key: {key}"

    # Ordering: track_date DESC (newest first) among V's rows.
    v_dates = [r["date"] for r in v_rows]
    assert v_dates == sorted(v_dates, reverse=True), (
        f"expected track_date DESC ordering, got {v_dates}"
    )


@pytest.mark.asyncio
async def test_vendor_endpoint_self_shape_baseline(api_client, seeder):
    """Task 3 / Property 4 (Preservation) — EXPECTED-PASS baseline.

    /vendor/{V}?date=D for the entitled creating client A returns the populated
    shape with points and stats. Characterizes the success response so Phase B
    cannot regress it.
    """
    a, b, v, days = await _seed_orphan_scenario(seeder)

    resp = await api_client.get(
        f"/api/tracks/vendor/{v.vendor_id}?date=2026-10-05",
        headers=_client_headers(a),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["vendor_id"] == v.vendor_id
    assert body["date"] == "2026-10-05"
    assert len(body.get("points", [])) == 2
    assert body.get("point_count") == 2
    assert body.get("stats") is not None
    assert "distance_km" in body["stats"]


@pytest.mark.asyncio
async def test_sync_and_me_write_self_read_untouched(api_client, seeder):
    """Task 3 / Property 4 (Preservation) — EXPECTED-PASS baseline.

    POST /api/tracks/sync (vendor-authed write) and GET /api/tracks/me (vendor
    self-read) behave as today. Out of scope for Phase B; characterized here so
    the fix cannot regress them.
    """
    a, b, v, days = await _seed_orphan_scenario(seeder)

    # Self-read of an existing orphan day via /me (vendor-authed).
    me_resp = await api_client.get(
        "/api/tracks/me?date=2026-10-05",
        headers=_vendor_headers(v, a),
    )
    assert me_resp.status_code == 200, me_resp.text
    me_body = me_resp.json()
    assert me_body["vendor_id"] == v.vendor_id
    assert me_body["date"] == "2026-10-05"
    assert me_body.get("point_count", 0) >= 1
    assert me_body.get("stats") is not None

    # Write path: /sync appends points to today's track for the authed vendor.
    # Record the track_id so teardown removes it (today's date, created by sync).
    sync_resp = await api_client.post(
        "/api/tracks/sync",
        headers=_vendor_headers(v, a),
        json={"points": [{"lat": 19.1, "lon": 72.9, "timestamp_ms": 1700000000000}]},
    )
    assert sync_resp.status_code == 200, sync_resp.text
    sync_body = sync_resp.json()
    assert sync_body["status"] == "synced"
    assert sync_body["points_received"] == 1
    assert "track_id" in sync_body
    # Ensure the sync-created "today" track is cleaned up by teardown.
    seeder.track_ids.append(uuid.UUID(sync_body["track_id"]))


# --------------------------------------------------------------------------- #
# Task 10 — /summary entitlement branches exercised directly
# --------------------------------------------------------------------------- #
async def _summary_vendor_dates(api_client, client, vendor_id):
    resp = await api_client.get(
        "/api/tracks/summary?start_date=2026-10-01&end_date=2026-10-31",
        headers=_client_headers(client),
    )
    assert resp.status_code == 200, resp.text
    return {r["date"] for r in resp.json()["rows"] if r["vendor_id"] == vendor_id}


@pytest.mark.asyncio
async def test_summary_in_window_branch(api_client, seeder):
    """IN-WINDOW: V assigned to A's campaign covering D -> /summary returns (V, D)
    for A and not for B."""
    async with TestSessionLocal() as s:
        a = await seeder.client(s, f"iwa_{uuid.uuid4().hex[:8]}@x.com", "In-window A")
        b = await seeder.client(s, f"iwb_{uuid.uuid4().hex[:8]}@x.com", "In-window B")
        v = await seeder.vendor(s, a)
        cam = await seeder.campaign(
            s, a,
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            datetime(2026, 10, 10, tzinfo=timezone.utc),
        )
        await seeder.assign(s, cam, v)
        await seeder.track(s, v, date(2026, 10, 5))
        await s.commit()

    assert await _summary_vendor_dates(api_client, a, v.vendor_id) == {"2026-10-05"}
    assert await _summary_vendor_dates(api_client, b, v.vendor_id) == set()


@pytest.mark.asyncio
async def test_summary_conflict_overlap_branch(api_client, seeder):
    """CONFLICT/OVERLAP: A's and B's campaigns both cover (V, D) -> both see it via
    their own campaign; a third client sees nothing."""
    async with TestSessionLocal() as s:
        a = await seeder.client(s, f"cfa_{uuid.uuid4().hex[:8]}@x.com", "Conflict A")
        b = await seeder.client(s, f"cfb_{uuid.uuid4().hex[:8]}@x.com", "Conflict B")
        c = await seeder.client(s, f"cfc_{uuid.uuid4().hex[:8]}@x.com", "Third C")
        v = await seeder.vendor(s, a)
        for owner in (a, b):
            cam = await seeder.campaign(
                s, owner,
                datetime(2026, 10, 1, tzinfo=timezone.utc),
                datetime(2026, 10, 31, tzinfo=timezone.utc),
            )
            await seeder.assign(s, cam, v)
        await seeder.track(s, v, date(2026, 10, 5))
        await s.commit()

    assert await _summary_vendor_dates(api_client, a, v.vendor_id) == {"2026-10-05"}
    assert await _summary_vendor_dates(api_client, b, v.vendor_id) == {"2026-10-05"}
    assert await _summary_vendor_dates(api_client, c, v.vendor_id) == set()
