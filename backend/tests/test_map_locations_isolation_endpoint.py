"""Phase C — Real endpoint-level two-client map isolation tests (Task 9).

Spec: .kiro/specs/map-tracking-isolation-fix (Task 9, refinement 4, map cases)

GET /api/photos/locations as client A vs client B on the SAME tenant must each
return only their own campaign's located features (legacy photos + evidence),
with no cross-client leakage in either direction.

Harness: dedicated NullPool engine + committed seeding with explicit teardown,
mirroring test_map_locations_isolation.py. Only rows created by this module's
seeder are ever written or deleted.
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
        self.client_ids: list = []
        self.campaign_ids: list = []
        self.vendor_ids: list = []
        self.evidence_ids: list = []
        self.photo_ids: list = []
        self.sensor_ids: list = []

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

    async def campaign(self, s, client):
        cam = Campaign(
            campaign_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID, client_id=client.client_id,
            campaign_code=f"CAM-{uuid.uuid4().hex[:8].upper()}", name="Endpoint Map Campaign",
            campaign_type=CampaignType.OOH_ADVERTISING,
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
            vendor_id=uuid.uuid4().hex[:6].upper(), tenant_id=DEFAULT_TENANT_ID,
            created_by_client_id=client.client_id, name="Endpoint Map Vendor",
            phone_number="+919000000000", status=VendorStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(v)
        await s.flush()
        self.vendor_ids.append(v.vendor_id)
        return v

    async def evidence(self, s, campaign, vendor, lat, lon, status="verified"):
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


@pytest.mark.asyncio
async def test_two_clients_same_tenant_see_only_their_own_evidence_and_legacy_locations(api_client, seeder):
    """A has evidence-only locations, B has legacy-only locations, same tenant.
    Each client's response must contain only its own features; no cross-client
    photo_id/campaign_code leakage in either direction."""
    async with TestSessionLocal() as s:
        a = await seeder.client(s, "mapA")
        b = await seeder.client(s, "mapB")
        cam_a = await seeder.campaign(s, a)
        cam_b = await seeder.campaign(s, b)
        va = await seeder.vendor(s, a)
        vb = await seeder.vendor(s, b)
        ev_a1 = await seeder.evidence(s, cam_a, va, 19.07, 72.87, "verified")
        ev_a2 = await seeder.evidence(s, cam_a, va, 19.08, 72.88, "rejected")
        legacy_b = await seeder.legacy_photo(s, cam_b, vb, 28.61, 77.20)
        await s.commit()

    resp_a = await api_client.get("/api/photos/locations", headers=_headers(a))
    resp_b = await api_client.get("/api/photos/locations", headers=_headers(b))
    assert resp_a.status_code == 200, resp_a.text
    assert resp_b.status_code == 200, resp_b.text

    a_ids = {f["properties"]["photo_id"] for f in resp_a.json()["features"]}
    b_ids = {f["properties"]["photo_id"] for f in resp_b.json()["features"]}

    assert a_ids == {str(ev_a1.evidence_id), str(ev_a2.evidence_id)}
    assert b_ids == {str(legacy_b.photo_id)}
    assert a_ids.isdisjoint(b_ids)

    a_codes = {f["properties"]["campaign_code"] for f in resp_a.json()["features"]}
    b_codes = {f["properties"]["campaign_code"] for f in resp_b.json()["features"]}
    assert cam_b.campaign_code not in a_codes
    assert cam_a.campaign_code not in b_codes


@pytest.mark.asyncio
async def test_two_clients_each_with_both_sources_no_cross_leak(api_client, seeder):
    """Each client has BOTH an evidence row and a legacy photo; verify the union
    is correctly scoped per-client with no mixing."""
    async with TestSessionLocal() as s:
        a = await seeder.client(s, "mixA")
        b = await seeder.client(s, "mixB")
        cam_a = await seeder.campaign(s, a)
        cam_b = await seeder.campaign(s, b)
        va = await seeder.vendor(s, a)
        vb = await seeder.vendor(s, b)
        ev_a = await seeder.evidence(s, cam_a, va, 19.07, 72.87, "verified")
        legacy_a = await seeder.legacy_photo(s, cam_a, va, 19.10, 72.90)
        ev_b = await seeder.evidence(s, cam_b, vb, 28.60, 77.19, "flagged")
        legacy_b = await seeder.legacy_photo(s, cam_b, vb, 28.61, 77.20)
        await s.commit()

    resp_a = await api_client.get("/api/photos/locations", headers=_headers(a))
    resp_b = await api_client.get("/api/photos/locations", headers=_headers(b))
    assert resp_a.status_code == 200, resp_a.text
    assert resp_b.status_code == 200, resp_b.text

    a_ids = {f["properties"]["photo_id"] for f in resp_a.json()["features"]}
    b_ids = {f["properties"]["photo_id"] for f in resp_b.json()["features"]}

    assert a_ids == {str(ev_a.evidence_id), str(legacy_a.photo_id)}
    assert b_ids == {str(ev_b.evidence_id), str(legacy_b.photo_id)}
    assert a_ids.isdisjoint(b_ids)
