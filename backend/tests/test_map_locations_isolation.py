"""Phase A characterization + preservation tests for the Map View bug (Bug 1).

Spec: .kiro/specs/map-tracking-isolation-fix  (Tasks 1 & 3, map portion)

Bug 1 (design Property 1 / isBugCondition_Map): GET /api/photos/locations reads
ONLY the legacy ``photos`` + ``sensor_data`` tables. A client whose geo-located
captures live only in the unified ``evidence`` table sees an empty
``FeatureCollection`` ("0 of 0 locations").

Tests in this module and what they map to:
  - test_evidence_only_client_sees_map_locations
        Task 1 / Property 1 (Bug Condition). Encodes the EXPECTED POST-FIX
        behavior. Marked xfail(strict=False): it FAILS on the current (unfixed)
        code (endpoint returns 0 evidence features) which PROVES Bug 1, and will
        xpass automatically once Phase B unions the evidence table.
  - test_legacy_only_client_sees_map_locations
        Task 3 / Property 2 (Preservation). EXPECTED-PASS baseline on current
        code; must stay green after the fix (legacy path + shape unchanged).
  - test_no_cross_client_map_leak
        Task 3 / Property 2 (Preservation). EXPECTED-PASS baseline: client A must
        never see client B's locations (campaign scoping) on the shared tenant.

Harness notes (OF-3 lesson):
  * The tenant-resolution middleware and the endpoint's own session run on the
    app-runtime ``AsyncSessionLocal`` (same test DB URL), NOT the rolled-back
    conftest ``db_session``. So any data the endpoint must SEE is seeded through a
    COMMITTED session (``TestSessionLocal``) with UNIQUE ids per test and is
    explicitly deleted in teardown so re-runs stay clean and isolated.
  * ``api_client`` overrides ``get_db`` with a FRESH committed session per call so
    the middleware and endpoint never share one asyncpg connection.
  * Two clients A and B share the SAME tenant id on purpose — single-tenant /
    multi-client isolation is the whole point of this bugfix.
  * These tests create and clean up only their OWN rows; no real/demo data is
    touched or deleted.

POST-FIX NOTE: the Bug 1 / Bug 2 tests below were xfail(strict=False) while the bugs existed (Phase A). Phase B fixed both, so the markers were removed; they are now plain regression guards and will FAIL (not xfail) if either bug returns.
"""
import os
import uuid
from datetime import datetime, timezone

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
from app.models.vendor import Vendor, VendorStatus
from app.models.evidence import Evidence
from app.models.photo import Photo, VerificationStatus
from app.models.sensor_data import SensorData

from tests.hotfix_support import TEST_DATABASE_URL, DEFAULT_TENANT_ID, hotfix_runtime_env  # noqa: F401

# Dedicated NullPool engine for this module. NullPool opens a fresh asyncpg
# connection for every checkout and closes it on release, so concurrently-live
# sessions (seed session + the endpoint/middleware sessions that run inside the
# same request) never contend on one pooled connection. This avoids the asyncpg
# "another operation is in progress" error seen when reusing the shared pooled
# engine across the per-test seed + endpoint calls on a single event loop.
_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def api_client() -> AsyncClient:
    """httpx AsyncClient over the app, with get_db overridden to a FRESH
    committed session per call (so middleware + endpoint don't share a
    connection)."""
    async def override_get_db():
        async with TestSessionLocal() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


class _Seeder:
    """Commits seed rows to the test DB and records ids for teardown.

    Deletes children before parents to satisfy FK constraints. Only rows this
    seeder created are removed, so other data (real/demo) is never touched.
    """

    def __init__(self):
        self.client_ids: list = []
        self.campaign_ids: list = []
        self.vendor_ids: list = []
        self.evidence_ids: list = []
        self.photo_ids: list = []
        self.sensor_ids: list = []

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

    async def campaign(self, s, client):
        cam = Campaign(
            campaign_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID,
            client_id=client.client_id,
            campaign_code=f"CAM-{uuid.uuid4().hex[:8].upper()}",
            name="Map Test Campaign", campaign_type=CampaignType.OOH_ADVERTISING,
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2027, 1, 1, tzinfo=timezone.utc),
            status=CampaignStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(cam)
        await s.flush()
        self.campaign_ids.append(cam.campaign_id)
        return cam

    async def vendor(self, s, client):
        v = Vendor(
            vendor_id=f"{uuid.uuid4().hex[:6].upper()}", tenant_id=DEFAULT_TENANT_ID,
            created_by_client_id=client.client_id, name="Map Vendor",
            phone_number="+919000000000", status=VendorStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(v)
        await s.flush()
        self.vendor_ids.append(v.vendor_id)
        return v

    async def evidence(self, s, campaign, vendor, lat, lon, status="rejected"):
        e = Evidence(
            evidence_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID,
            campaign_id=campaign.campaign_id, vendor_id=vendor.vendor_id,
            evidence_type="photo", latitude=lat, longitude=lon,
            verification_status=status, verification_confidence=0.5,
            verification_flags=[], file_url="https://res.cloudinary.com/demo/x.jpg",
            thumbnail_url="https://res.cloudinary.com/demo/x_t.jpg",
            file_hash="h" * 64,
            capture_timestamp=datetime(2026, 10, 5, tzinfo=timezone.utc),
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(e)
        await s.flush()
        self.evidence_ids.append(e.evidence_id)
        return e

    async def legacy_photo(self, s, campaign, vendor, lat, lon):
        pid = uuid.uuid4()
        p = Photo(
            photo_id=pid, tenant_id=DEFAULT_TENANT_ID, campaign_id=campaign.campaign_id,
            vendor_id=vendor.vendor_id, s3_key=f"photos/{pid}.jpg",
            verification_status=VerificationStatus.VERIFIED, signature_valid=True,
            capture_timestamp=datetime(2026, 10, 5, tzinfo=timezone.utc),
            upload_timestamp=datetime.now(tz=timezone.utc),
            created_at=datetime.now(tz=timezone.utc),
        )
        s.add(p)
        await s.flush()
        self.photo_ids.append(pid)
        sd = SensorData(
            sensor_data_id=uuid.uuid4(), photo_id=pid, gps_latitude=lat,
            gps_longitude=lon, gps_accuracy=5.0,
            created_at=datetime.now(tz=timezone.utc),
        )
        s.add(sd)
        await s.flush()
        self.sensor_ids.append(sd.sensor_data_id)
        return p

    async def cleanup(self):
        async with TestSessionLocal() as s:
            if self.sensor_ids:
                await s.execute(delete(SensorData).where(SensorData.sensor_data_id.in_(self.sensor_ids)))
            if self.photo_ids:
                await s.execute(delete(Photo).where(Photo.photo_id.in_(self.photo_ids)))
            if self.evidence_ids:
                await s.execute(delete(Evidence).where(Evidence.evidence_id.in_(self.evidence_ids)))
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


# --------------------------------------------------------------------------- #
# Task 1 — bug characterization (EXPECTED-FAIL pre-fix -> xpass post-fix)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_evidence_only_client_sees_map_locations(api_client, seeder):
    """Task 1 / Property 1 (Bug Condition) — EXPECTED-FAIL pre-fix.

    An evidence-only client (no legacy photos) with several located evidence rows
    of mixed verification_status (incl. 'rejected') must get one map feature per
    located evidence row, regardless of status. Unfixed endpoint queries only the
    legacy photos table, so it returns an empty FeatureCollection (0 features) —
    that failure proves Bug 1.
    """
    async with TestSessionLocal() as s:
        c = await seeder.client(s, f"ev_{uuid.uuid4().hex[:8]}@x.com", "Evidence Only Co")
        cam = await seeder.campaign(s, c)
        v = await seeder.vendor(s, c)
        await seeder.evidence(s, cam, v, 19.07, 72.87, "rejected")
        await seeder.evidence(s, cam, v, 19.08, 72.88, "verified")
        await seeder.evidence(s, cam, v, 19.09, 72.89, "flagged")
        await seeder.evidence(s, cam, v, 19.10, 72.90, "pending")
        await s.commit()

    resp = await api_client.get("/api/photos/locations", headers=_headers(c))
    assert resp.status_code == 200, resp.text
    feats = resp.json().get("features", [])

    # EXPECTED POST-FIX: one feature per located evidence row, any status.
    assert len(feats) == 4, (
        f"expected 4 evidence features, got {len(feats)} "
        f"(Bug 1: evidence-only client sees 0 map locations)"
    )
    returned_ids = {f["properties"]["photo_id"] for f in feats}
    assert returned_ids == {str(eid) for eid in seeder.evidence_ids}
    statuses = {f["properties"]["status"] for f in feats}
    assert {"rejected", "verified", "flagged", "pending"} <= statuses


# --------------------------------------------------------------------------- #
# Task 3 (map) — preservation baselines (EXPECTED-PASS now and after fix)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_legacy_only_client_sees_map_locations(api_client, seeder):
    """Task 3 / Property 2 (Preservation) — EXPECTED-PASS baseline.

    A legacy-only client (photos + sensor_data, no evidence) still gets its legacy
    features with the existing FeatureCollection shape and property keys.
    """
    async with TestSessionLocal() as s:
        c = await seeder.client(s, f"lg_{uuid.uuid4().hex[:8]}@x.com", "Legacy Only Co")
        cam = await seeder.campaign(s, c)
        v = await seeder.vendor(s, c)
        await seeder.legacy_photo(s, cam, v, 28.61, 77.20)
        await s.commit()

    resp = await api_client.get("/api/photos/locations", headers=_headers(c))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    feats = body.get("features", [])
    assert len(feats) == 1

    feat = feats[0]
    assert feat["geometry"]["type"] == "Point"
    # GPS values are stored as single-precision Float, so compare with tolerance.
    lon, lat = feat["geometry"]["coordinates"]
    assert lon == pytest.approx(77.20, abs=1e-3)
    assert lat == pytest.approx(28.61, abs=1e-3)
    props = feat["properties"]
    for key in ("photo_id", "status", "confidence", "flags", "campaign_name",
                "campaign_code", "vendor_name", "photo_url", "thumbnail_url",
                "captured_at"):
        assert key in props, f"legacy feature missing property key: {key}"
    assert props["photo_id"] == str(seeder.photo_ids[0])
    assert props["campaign_code"] == cam.campaign_code


@pytest.mark.asyncio
async def test_no_cross_client_map_leak(api_client, seeder):
    """Task 3 / Property 2 (Preservation) — EXPECTED-PASS baseline.

    On the shared tenant, client A must not see client B's locations via the
    legacy path. We assert A's response contains none of B's campaign code.
    """
    async with TestSessionLocal() as s:
        a = await seeder.client(s, f"a_{uuid.uuid4().hex[:8]}@x.com", "Client A")
        b = await seeder.client(s, f"b_{uuid.uuid4().hex[:8]}@x.com", "Client B")
        cam_a = await seeder.campaign(s, a)
        cam_b = await seeder.campaign(s, b)
        va = await seeder.vendor(s, a)
        vb = await seeder.vendor(s, b)
        await seeder.legacy_photo(s, cam_a, va, 28.61, 77.20)
        await seeder.legacy_photo(s, cam_b, vb, 19.07, 72.87)
        await s.commit()

    resp_a = await api_client.get("/api/photos/locations", headers=_headers(a))
    assert resp_a.status_code == 200, resp_a.text
    a_codes = {f["properties"]["campaign_code"] for f in resp_a.json().get("features", [])}
    assert cam_a.campaign_code in a_codes
    assert cam_b.campaign_code not in a_codes, "cross-client leak: A saw B's campaign"
