"""
Quick Capture (campaign-free evidence) visibility & authorization tests — Option A.

Shared predicate under test for campaign-free evidence (campaign_id IS NULL):
  visible iff an ACTIVE VendorClientAssociation links the evidence.vendor_id to
  the authenticated client, AND vendor/association/client/evidence tenants all
  agree. No created_by_client_id union. Campaign-bound access is unchanged.

Surfaces exercised end-to-end (real ASGI + real Postgres test DB):
  GET /api/photos               (Gallery list)
  GET /api/photos/locations     (Map)
  GET /api/reports/statistics   (counts)
  GET /api/reports/table-data   (report detail)

Tests assert SECURE, CONSISTENT behavior: they fail on the current code
(Map/Statistics exclude Quick Capture; Gallery/table-data lack ACTIVE+tenant
guards) and pass after Option A.
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
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from tests.hotfix_support import TEST_DATABASE_URL, DEFAULT_TENANT_ID, hotfix_runtime_env  # noqa: F401
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.client import Client, SubscriptionTier, SubscriptionStatus
from app.models.vendor import Vendor, VendorStatus
from app.models.vendor_client_association import VendorClientAssociation, AssociationStatus
from app.models.evidence import Evidence
from app.models.tenant_config import TenantConfig

_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool)
_Sessions = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

OTHER_TENANT_ID = uuid.UUID("c1c2c3c4-d1d2-4e3e-8f4f-aaaaaaaaaaaa")


@pytest_asyncio.fixture(autouse=True)
async def _ensure_other_tenant(setup_test_database):
    async with _Sessions() as s:
        from sqlalchemy import select
        exists = (await s.execute(
            select(TenantConfig.tenant_id).where(TenantConfig.tenant_id == OTHER_TENANT_ID)
        )).scalar_one_or_none()
        if not exists:
            s.add(TenantConfig(
                tenant_id=OTHER_TENANT_ID, tenant_name="Other Tenant",
                subdomain=f"qc-other-{OTHER_TENANT_ID.hex[:6]}", is_active=True,
                created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
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


# --------------------------------------------------------------------------- #
# Seeder: builds clients, vendors, associations, and campaign-free evidence.
# Tracks every id for teardown; only touches rows it created.
# --------------------------------------------------------------------------- #
class _Seed:
    def __init__(self):
        self.client_ids = []
        self.vendor_ids = []
        self.assoc_ids = []
        self.evidence_ids = []

    async def client(self, s, tenant=DEFAULT_TENANT_ID):
        c = Client(
            client_id=uuid.uuid4(), tenant_id=tenant,
            email=f"qc_{uuid.uuid4().hex[:10]}@test.invalid",
            password_hash=hash_password("Pass!1234"),
            company_name="QC Co", phone_number="+10000000000",
            subscription_tier=SubscriptionTier.FREE,
            subscription_status=SubscriptionStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(c); self.client_ids.append(c.client_id); return c

    async def vendor(self, s, creator, tenant=DEFAULT_TENANT_ID):
        v = Vendor(
            vendor_id=uuid.uuid4().hex[:6].upper(), tenant_id=tenant,
            created_by_client_id=creator.client_id, name="QC Vendor",
            phone_number="+919000000000", status=VendorStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(v); self.vendor_ids.append(v.vendor_id); return v

    async def assoc(self, s, vendor, client, status=AssociationStatus.ACTIVE, tenant=None):
        a = VendorClientAssociation(
            association_id=uuid.uuid4(), vendor_id=vendor.vendor_id, client_id=client.client_id,
            tenant_id=tenant or client.tenant_id, status=status,
            enrolled_at=datetime.now(tz=timezone.utc),
        )
        s.add(a); self.assoc_ids.append(a.association_id); return a

    async def quick_capture(self, s, vendor, tenant=DEFAULT_TENANT_ID,
                            lat=19.0760, lon=72.8777, status="verified"):
        e = Evidence(
            tenant_id=tenant, vendor_id=vendor.vendor_id, campaign_id=None,
            evidence_type="photo", verification_status=status,
            latitude=lat, longitude=lon,
            file_url="https://example.invalid/qc.jpg",
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(e); return e  # evidence_id captured after flush/refresh

    async def finalize(self, s, *evidences):
        await s.commit()
        for e in evidences:
            await s.refresh(e)
            self.evidence_ids.append(e.evidence_id)

    async def cleanup(self):
        async with _Sessions() as s:
            if self.evidence_ids:
                await s.execute(delete(Evidence).where(Evidence.evidence_id.in_(self.evidence_ids)))
            if self.assoc_ids:
                await s.execute(delete(VendorClientAssociation).where(
                    VendorClientAssociation.association_id.in_(self.assoc_ids)))
            if self.vendor_ids:
                await s.execute(delete(Vendor).where(Vendor.vendor_id.in_(self.vendor_ids)))
            if self.client_ids:
                await s.execute(delete(Client).where(Client.client_id.in_(self.client_ids)))
            await s.commit()


@pytest_asyncio.fixture
async def seed():
    sd = _Seed()
    yield sd
    await sd.cleanup()


def _headers(client):
    token = create_access_token({"sub": str(client.client_id), "type": "client", "email": client.email})
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(client.tenant_id)}


# --------------------------------------------------------------------------- #
# Surface helpers: return the set of evidence/photo ids each surface shows.
# --------------------------------------------------------------------------- #
async def gallery_ids(api_client, client):
    r = await api_client.get("/api/photos?limit=200", headers=_headers(client))
    assert r.status_code == 200, r.text
    return {row["photo_id"] for row in r.json()}

async def map_ids(api_client, client):
    r = await api_client.get("/api/photos/locations", headers=_headers(client))
    assert r.status_code == 200, r.text
    return {f["properties"]["photo_id"] for f in r.json().get("features", [])}

async def stats(api_client, client):
    r = await api_client.get("/api/reports/statistics", headers=_headers(client))
    assert r.status_code == 200, r.text
    return r.json()

async def table_ids(api_client, client):
    r = await api_client.get("/api/reports/table-data", headers=_headers(client))
    assert r.status_code == 200, r.text
    body = r.json()
    rows = body if isinstance(body, list) else body.get("rows", body.get("data", []))
    return {row["photo_id"] for row in rows}


# --------------------------------------------------------------------------- #
# 1. Single ACTIVE client — visible on ALL surfaces, counted once
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_single_active_client_sees_quick_capture_all_surfaces(api_client, seed):
    async with _Sessions() as s:
        a = await seed.client(s)
        v = await seed.vendor(s, a)
        await seed.assoc(s, v, a, AssociationStatus.ACTIVE)
        e = await seed.quick_capture(s, v)
        await seed.finalize(s, e)
    eid = str(e.evidence_id)

    assert eid in await gallery_ids(api_client, a)
    assert eid in await map_ids(api_client, a)
    assert eid in await table_ids(api_client, a)
    st = await stats(api_client, a)
    assert st["total_photos"] >= 1
    # verified status => counted in verified bucket
    assert st["verified_photos"] >= 1


# --------------------------------------------------------------------------- #
# 2. INACTIVE association — NOT visible on any surface
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_inactive_association_hidden_all_surfaces(api_client, seed):
    async with _Sessions() as s:
        a = await seed.client(s)
        v = await seed.vendor(s, a)
        await seed.assoc(s, v, a, AssociationStatus.INACTIVE)
        e = await seed.quick_capture(s, v)
        await seed.finalize(s, e)
    eid = str(e.evidence_id)

    assert eid not in await gallery_ids(api_client, a)
    assert eid not in await map_ids(api_client, a)
    assert eid not in await table_ids(api_client, a)


# --------------------------------------------------------------------------- #
# 3. One ACTIVE + one INACTIVE client — only the active client sees it
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_one_active_one_inactive(api_client, seed):
    async with _Sessions() as s:
        active = await seed.client(s)
        inactive = await seed.client(s)
        v = await seed.vendor(s, active)
        await seed.assoc(s, v, active, AssociationStatus.ACTIVE)
        await seed.assoc(s, v, inactive, AssociationStatus.INACTIVE)
        e = await seed.quick_capture(s, v)
        await seed.finalize(s, e)
    eid = str(e.evidence_id)

    assert eid in await gallery_ids(api_client, active)
    assert eid not in await gallery_ids(api_client, inactive)
    assert eid not in await map_ids(api_client, inactive)
    assert eid not in await table_ids(api_client, inactive)


# --------------------------------------------------------------------------- #
# 4. Multiple ACTIVE clients (same tenant) — interim rule: both associated see it
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_multiple_active_clients_both_see(api_client, seed):
    async with _Sessions() as s:
        a = await seed.client(s)
        b = await seed.client(s)
        unrelated = await seed.client(s)
        v = await seed.vendor(s, a)
        await seed.assoc(s, v, a, AssociationStatus.ACTIVE)
        await seed.assoc(s, v, b, AssociationStatus.ACTIVE)
        e = await seed.quick_capture(s, v)
        await seed.finalize(s, e)
    eid = str(e.evidence_id)

    assert eid in await gallery_ids(api_client, a)
    assert eid in await gallery_ids(api_client, b)
    assert eid not in await gallery_ids(api_client, unrelated)


# --------------------------------------------------------------------------- #
# 5. Cross-tenant mismatch — client in another tenant must never see it
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_cross_tenant_mismatch_hidden(api_client, seed):
    async with _Sessions() as s:
        a = await seed.client(s, tenant=DEFAULT_TENANT_ID)
        v = await seed.vendor(s, a, tenant=DEFAULT_TENANT_ID)
        await seed.assoc(s, v, a, AssociationStatus.ACTIVE)
        e = await seed.quick_capture(s, v, tenant=DEFAULT_TENANT_ID)
        # Attacker client in OTHER tenant, with a deliberately-inconsistent ACTIVE
        # association row pointing at the foreign vendor (tenant mismatch).
        z = await seed.client(s, tenant=OTHER_TENANT_ID)
        await seed.assoc(s, v, z, AssociationStatus.ACTIVE, tenant=OTHER_TENANT_ID)
        await seed.finalize(s, e)
    eid = str(e.evidence_id)

    # z is in OTHER tenant; the four-way tenant guard must block visibility.
    assert eid not in await gallery_ids(api_client, z)
    assert eid not in await map_ids(api_client, z)
    assert eid not in await table_ids(api_client, z)


# --------------------------------------------------------------------------- #
# 6. Invalid / missing GPS — in Gallery, excluded from Map, present in stats
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_invalid_gps_excluded_from_map_only(api_client, seed):
    async with _Sessions() as s:
        a = await seed.client(s)
        v = await seed.vendor(s, a)
        await seed.assoc(s, v, a, AssociationStatus.ACTIVE)
        e = await seed.quick_capture(s, v, lat=None, lon=None)
        await seed.finalize(s, e)
    eid = str(e.evidence_id)

    assert eid in await gallery_ids(api_client, a)      # list shows it
    assert eid not in await map_ids(api_client, a)      # map excludes (no coords)
    st = await stats(api_client, a)
    assert st["total_photos"] >= 1                      # counted in stats


# --------------------------------------------------------------------------- #
# 7. Campaign-specific filter — selecting a campaign excludes campaign-free rows
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_campaign_filter_excludes_quick_capture(api_client, seed):
    """Filtering the Gallery to a REAL owned campaign returns that campaign's
    evidence and excludes campaign-free Quick Capture."""
    from app.models.campaign import Campaign, CampaignType, CampaignStatus
    async with _Sessions() as s:
        a = await seed.client(s)
        v = await seed.vendor(s, a)
        await seed.assoc(s, v, a, AssociationStatus.ACTIVE)
        qc = await seed.quick_capture(s, v)                      # campaign-free
        code = f"QC-{uuid.uuid4().hex[:8].upper()}"
        cam = Campaign(
            campaign_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID, client_id=a.client_id,
            campaign_code=code, name="Owned",
            campaign_type=CampaignType.OOH_ADVERTISING,
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
            status=CampaignStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(cam)
        cb = Evidence(                                           # campaign-bound
            tenant_id=DEFAULT_TENANT_ID, vendor_id=v.vendor_id, campaign_id=cam.campaign_id,
            evidence_type="photo", verification_status="verified",
            latitude=19.0, longitude=72.0, file_url="https://example.invalid/cb.jpg",
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(cb)
        await seed.finalize(s, qc, cb)
        cam_id = cam.campaign_id
    qc_id, cb_id = str(qc.evidence_id), str(cb.evidence_id)
    try:
        # Unfiltered: both visible
        allids = await gallery_ids(api_client, a)
        assert qc_id in allids and cb_id in allids
        # Filtered to the owned campaign: campaign-bound included, Quick Capture excluded
        r = await api_client.get(f"/api/photos?limit=200&campaign_code={code}", headers=_headers(a))
        assert r.status_code == 200, r.text
        ids = {row["photo_id"] for row in r.json()}
        assert cb_id in ids, "campaign-bound evidence must appear under its campaign filter"
        assert qc_id not in ids, "campaign-free Quick Capture must be excluded by a campaign filter"
    finally:
        async with _Sessions() as s:
            from app.models.campaign import Campaign as C
            await s.execute(delete(C).where(C.campaign_id == cam_id))
            await s.commit()


# --------------------------------------------------------------------------- #
# 8. Statistics consistency + duplicate-count prevention (counted exactly once)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_statistics_counts_quick_capture_once(api_client, seed):
    async with _Sessions() as s:
        a = await seed.client(s)
        v = await seed.vendor(s, a)
        await seed.assoc(s, v, a, AssociationStatus.ACTIVE)
        e1 = await seed.quick_capture(s, v, status="verified")
        e2 = await seed.quick_capture(s, v, status="rejected")
        await seed.finalize(s, e1, e2)

    st = await stats(api_client, a)
    # Exactly the two quick captures counted (plus any campaign photos = 0 here).
    assert st["total_photos"] == 2, st
    verified = st["verified_photos"]
    rejected = st["failed_photos"]          # rejected is surfaced as failed_photos
    pending = st["pending_photos"]
    assert verified == 1, st
    assert rejected == 1, st
    # No double counting: total == verified + failed + pending
    assert verified + rejected + pending == st["total_photos"], st


# --------------------------------------------------------------------------- #
# 9. Cross-surface authorization PARITY — same (client,capture) decision everywhere
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_cross_surface_parity_active_vs_inactive(api_client, seed):
    async with _Sessions() as s:
        active = await seed.client(s)
        inactive = await seed.client(s)
        v = await seed.vendor(s, active)
        await seed.assoc(s, v, active, AssociationStatus.ACTIVE)
        await seed.assoc(s, v, inactive, AssociationStatus.INACTIVE)
        e = await seed.quick_capture(s, v)
        await seed.finalize(s, e)
    eid = str(e.evidence_id)

    # Active client: visible on gallery, map, table (GPS present) -> parity TRUE
    g = eid in await gallery_ids(api_client, active)
    m = eid in await map_ids(api_client, active)
    t = eid in await table_ids(api_client, active)
    assert g and m and t, f"active parity broken: gallery={g} map={m} table={t}"

    # Inactive client: hidden everywhere -> parity FALSE
    g2 = eid in await gallery_ids(api_client, inactive)
    m2 = eid in await map_ids(api_client, inactive)
    t2 = eid in await table_ids(api_client, inactive)
    assert not (g2 or m2 or t2), f"inactive leak: gallery={g2} map={m2} table={t2}"


# --------------------------------------------------------------------------- #
# 10. Campaign-bound authorization regression — unchanged by Option A
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_campaign_bound_access_unchanged(api_client, seed):
    """A client must NOT see campaign-bound evidence of a campaign it doesn't own,
    and the quick-capture predicate must not accidentally widen this."""
    from app.models.campaign import Campaign, CampaignType, CampaignStatus
    async with _Sessions() as s:
        owner = await seed.client(s)
        other = await seed.client(s)
        v = await seed.vendor(s, owner)
        await seed.assoc(s, v, owner, AssociationStatus.ACTIVE)
        await seed.assoc(s, v, other, AssociationStatus.ACTIVE)  # shares vendor, different campaigns
        cam = Campaign(
            campaign_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID, client_id=owner.client_id,
            campaign_code=f"QC-{uuid.uuid4().hex[:8].upper()}", name="Owned",
            campaign_type=CampaignType.OOH_ADVERTISING,
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
            status=CampaignStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(cam)
        ev = Evidence(
            tenant_id=DEFAULT_TENANT_ID, vendor_id=v.vendor_id, campaign_id=cam.campaign_id,
            evidence_type="photo", verification_status="verified",
            latitude=19.0, longitude=72.0, file_url="https://example.invalid/c.jpg",
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(ev)
        await s.commit(); await s.refresh(ev)
        seed.evidence_ids.append(ev.evidence_id)
        # track campaign for teardown
        cam_id = cam.campaign_id
    eid = str(ev.evidence_id)
    try:
        # Owner sees its campaign-bound evidence
        assert eid in await gallery_ids(api_client, owner)
        # The OTHER client (shares the vendor but not the campaign) must NOT see
        # a CAMPAIGN-BOUND row via the quick-capture predicate.
        assert eid not in await gallery_ids(api_client, other)
        assert eid not in await table_ids(api_client, other)
    finally:
        async with _Sessions() as s:
            from app.models.campaign import Campaign as C
            await s.execute(delete(C).where(C.campaign_id == cam_id))
            await s.commit()


# --------------------------------------------------------------------------- #
# 11. Map response structure unchanged; valid GPS renders; invalid GPS excluded
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_map_structure_unchanged_and_valid_gps_renders(api_client, seed):
    from app.models.campaign import Campaign, CampaignType, CampaignStatus
    async with _Sessions() as s:
        a = await seed.client(s)
        v = await seed.vendor(s, a)
        await seed.assoc(s, v, a, AssociationStatus.ACTIVE)
        qc_ok = await seed.quick_capture(s, v, lat=19.0760, lon=72.8777)
        qc_bad = await seed.quick_capture(s, v, lat=95.0, lon=72.8777)   # out of range
        cam = Campaign(
            campaign_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID, client_id=a.client_id,
            campaign_code=f"QC-{uuid.uuid4().hex[:8].upper()}", name="Owned",
            campaign_type=CampaignType.OOH_ADVERTISING,
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
            status=CampaignStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(cam)
        cb = Evidence(
            tenant_id=DEFAULT_TENANT_ID, vendor_id=v.vendor_id, campaign_id=cam.campaign_id,
            evidence_type="photo", verification_status="verified",
            latitude=18.5204, longitude=73.8567, file_url="https://example.invalid/cb.jpg",
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(cb)
        await seed.finalize(s, qc_ok, qc_bad, cb)
        cam_id = cam.campaign_id
    try:
        r = await api_client.get("/api/photos/locations", headers=_headers(a))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["type"] == "FeatureCollection"
        feats = {f["properties"]["photo_id"]: f for f in body["features"]}

        ok_id, bad_id, cb_id = str(qc_ok.evidence_id), str(qc_bad.evidence_id), str(cb.evidence_id)
        assert ok_id in feats and cb_id in feats
        assert bad_id not in feats, "out-of-range coordinates must never render on the map"

        f_ok, f_cb = feats[ok_id], feats[cb_id]
        for f in (f_ok, f_cb):
            assert f["type"] == "Feature"
            assert f["geometry"]["type"] == "Point"
        # GeoJSON order is [lon, lat]
        assert f_ok["geometry"]["coordinates"] == [72.8777, 19.076]
        # Same property schema for Quick Capture and campaign-bound features
        assert set(f_ok["properties"].keys()) == set(f_cb["properties"].keys())
        expected = {"photo_id", "status", "confidence", "flags", "campaign_name",
                    "campaign_code", "vendor_name", "photo_url", "thumbnail_url", "captured_at"}
        assert expected <= set(f_ok["properties"].keys())
        assert f_ok["properties"]["status"] == "verified"
        # The invalid-GPS capture still appears in the Gallery (list is not GPS-gated)
        assert bad_id in await gallery_ids(api_client, a)
    finally:
        async with _Sessions() as s:
            from app.models.campaign import Campaign as C
            await s.execute(delete(C).where(C.campaign_id == cam_id))
            await s.commit()


# --------------------------------------------------------------------------- #
# 12. Statistics classification: pending / verified / rejected / flagged, count-once,
#     parity with the Gallery, exclusion of unauthorized rows
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_statistics_classification_and_count_once(api_client, seed):
    from app.models.campaign import Campaign, CampaignType, CampaignStatus
    async with _Sessions() as s:
        a = await seed.client(s)
        outsider = await seed.client(s)
        v = await seed.vendor(s, a)
        await seed.assoc(s, v, a, AssociationStatus.ACTIVE)
        # Vendor linked to the outsider only via an INACTIVE association -> never counted for a
        v_inactive = await seed.vendor(s, outsider)
        await seed.assoc(s, v_inactive, a, AssociationStatus.INACTIVE)

        q_ver = await seed.quick_capture(s, v, status="verified")
        q_rej = await seed.quick_capture(s, v, status="rejected")
        q_pen = await seed.quick_capture(s, v, status="pending")
        q_flg = await seed.quick_capture(s, v, status="flagged")
        q_hidden = await seed.quick_capture(s, v_inactive, status="verified")   # must NOT count for a

        cam = Campaign(
            campaign_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID, client_id=a.client_id,
            campaign_code=f"QC-{uuid.uuid4().hex[:8].upper()}", name="Owned",
            campaign_type=CampaignType.OOH_ADVERTISING,
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
            status=CampaignStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(cam)
        cb = Evidence(
            tenant_id=DEFAULT_TENANT_ID, vendor_id=v.vendor_id, campaign_id=cam.campaign_id,
            evidence_type="photo", verification_status="verified",
            latitude=19.0, longitude=72.0, file_url="https://example.invalid/cb.jpg",
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(cb)
        await seed.finalize(s, q_ver, q_rej, q_pen, q_flg, q_hidden, cb)
        cam_id = cam.campaign_id
    try:
        st = await stats(api_client, a)
        # visible to a: 4 quick captures + 1 campaign-bound = 5 (q_hidden excluded)
        assert st["total_photos"] == 5, st
        assert st["verified_photos"] == 2, st      # q_ver + cb
        assert st["failed_photos"] == 1, st        # q_rej
        assert st["pending_photos"] == 2, st       # q_pen + q_flg (non-verified, non-rejected)
        assert st["verified_photos"] + st["failed_photos"] + st["pending_photos"] == st["total_photos"]

        # Parity: the Gallery lists exactly the same evidence rows that Statistics counts
        ids = await gallery_ids(api_client, a)
        expected = {str(e.evidence_id) for e in (q_ver, q_rej, q_pen, q_flg, cb)}
        assert expected <= ids
        assert str(q_hidden.evidence_id) not in ids
        assert len([i for i in ids if i in expected]) == 5   # each counted once, no duplicates
    finally:
        async with _Sessions() as s:
            from app.models.campaign import Campaign as C
            await s.execute(delete(C).where(C.campaign_id == cam_id))
            await s.commit()


# --------------------------------------------------------------------------- #
# 13. Campaign-bound TENANT GUARD: an evidence row stamped with ANOTHER tenant
#     must never be visible to a client just because its campaign_id points at
#     that client's campaign (e.g. via an unvalidated upload campaign_id).
#     Applies to Gallery, Map, Statistics and report detail alike.
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_campaign_bound_cross_tenant_evidence_hidden_all_surfaces(api_client, seed):
    from app.models.campaign import Campaign, CampaignType, CampaignStatus
    async with _Sessions() as s:
        a = await seed.client(s, tenant=DEFAULT_TENANT_ID)
        z = await seed.client(s, tenant=OTHER_TENANT_ID)
        vz = await seed.vendor(s, z, tenant=OTHER_TENANT_ID)
        va = await seed.vendor(s, a, tenant=DEFAULT_TENANT_ID)
        await seed.assoc(s, va, a, AssociationStatus.ACTIVE)
        cam = Campaign(
            campaign_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID, client_id=a.client_id,
            campaign_code=f"TG-{uuid.uuid4().hex[:8].upper()}", name="A-owned",
            campaign_type=CampaignType.OOH_ADVERTISING,
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
            status=CampaignStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(cam)
        # Foreign-tenant evidence that references A's campaign
        foreign = Evidence(
            tenant_id=OTHER_TENANT_ID, vendor_id=vz.vendor_id, campaign_id=cam.campaign_id,
            evidence_type="photo", verification_status="verified",
            latitude=19.0, longitude=72.0, file_url="https://example.invalid/foreign.jpg",
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        # Legitimate same-tenant evidence on the same campaign (must stay visible)
        legit = Evidence(
            tenant_id=DEFAULT_TENANT_ID, vendor_id=va.vendor_id, campaign_id=cam.campaign_id,
            evidence_type="photo", verification_status="verified",
            latitude=19.1, longitude=72.1, file_url="https://example.invalid/legit.jpg",
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(foreign); s.add(legit)
        await seed.finalize(s, foreign, legit)
        cam_id = cam.campaign_id
    f_id, l_id = str(foreign.evidence_id), str(legit.evidence_id)
    try:
        g, m, t = await gallery_ids(api_client, a), await map_ids(api_client, a), await table_ids(api_client, a)
        # Foreign-tenant row hidden on every surface
        assert f_id not in g, "foreign-tenant evidence leaked into Gallery"
        assert f_id not in m, "foreign-tenant evidence leaked into Map"
        assert f_id not in t, "foreign-tenant evidence leaked into report detail"
        # Same-tenant campaign-bound row still visible on every surface
        assert l_id in g and l_id in m and l_id in t
        # Statistics count only the legitimate row
        st = await stats(api_client, a)
        assert st["total_photos"] == 1, st
        assert st["verified_photos"] == 1, st
    finally:
        async with _Sessions() as s:
            from app.models.campaign import Campaign as C
            await s.execute(delete(C).where(C.campaign_id == cam_id))
            await s.commit()
