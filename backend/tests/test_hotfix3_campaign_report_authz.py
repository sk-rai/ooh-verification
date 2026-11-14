"""
Hotfix 3 — campaign report and campaign-photos ownership authorization.

Rule under test: a client may read a campaign's reports/photos ONLY if
    Campaign.client_id == authenticated client_id
AND Campaign.tenant_id == authenticated client tenant_id.
Anyone else (same-tenant non-owner, foreign tenant, nonexistent code) gets an
identical, non-disclosing 404 and receives no records, GPS, storage keys or
campaign data.

Covers every ReportGenerator entry point:
  GET /api/reports/campaigns/{code}/csv | geojson | pdf | statistics | dashboard
  GET /api/reports/campaigns/{code}/charts/{verification|confidence|timeline}
  GET /api/campaigns/{id}/photos
  ReportGenerator methods called directly, and the generate_pdf queue handler.

Tests go through the real ASGI app against the isolated test database.
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
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from tests.hotfix_support import TEST_DATABASE_URL, DEFAULT_TENANT_ID, hotfix_runtime_env  # noqa: F401
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Photo, SensorData
from app.models.photo import VerificationStatus
from app.models.campaign import Campaign, CampaignType, CampaignStatus
from app.models.client import Client, SubscriptionTier, SubscriptionStatus
from app.models.tenant_config import TenantConfig
from app.models.vendor import Vendor, VendorStatus
from app.services.chart_generator import ChartGenerator
from app.services.map_generator import MapGenerator
from app.services.report_generator import ReportGenerator

_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool)
_Sessions = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

OTHER_TENANT_ID = uuid.UUID("d1d2d3d4-e1e2-4f3f-8a4a-bbbbbbbbbbbb")

# Sentinels that must NEVER appear in a response to an unauthorized caller.
LAT, LON = 12.34375, 77.765625          # exactly representable in the column's float precision
LAT_S, LON_S = "12.34375", "77.765625"



@pytest.fixture(autouse=True)
def _stub_pdf_renderer(monkeypatch):
    """reportlab may be absent in the test env. The PDF route and the generate_pdf queue
    handler import app.services.pdf_generator at call time; stub it so the REAL ownership
    lookup runs and rendering is irrelevant to what these tests assert."""
    import sys
    import types
    fake = types.ModuleType("app.services.pdf_generator")

    class PDFGenerator:
        def generate_campaign_report(self, campaign_data, statistics, chart_images):
            return b"%PDF-1.4 hotfix3-stub"

    fake.PDFGenerator = PDFGenerator
    monkeypatch.setitem(sys.modules, "app.services.pdf_generator", fake)
    yield


@pytest_asyncio.fixture(autouse=True)
async def _ensure_other_tenant(setup_test_database):
    async with _Sessions() as s:
        exists = (await s.execute(
            select(TenantConfig.tenant_id).where(TenantConfig.tenant_id == OTHER_TENANT_ID)
        )).scalar_one_or_none()
        if not exists:
            s.add(TenantConfig(
                tenant_id=OTHER_TENANT_ID, tenant_name="H3 Other Tenant",
                subdomain=f"h3-other-{OTHER_TENANT_ID.hex[:6]}", is_active=True,
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


def _headers(client):
    token = create_access_token({"sub": str(client.client_id), "type": "client", "email": client.email})
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(client.tenant_id)}


def _mk_client(tenant, tag):
    return Client(
        client_id=uuid.uuid4(), tenant_id=tenant,
        email=f"h3_{tag}_{uuid.uuid4().hex[:8]}@test.invalid",
        password_hash=hash_password("Pass!1234"), company_name=f"H3 {tag}",
        phone_number="+10000000000",
        subscription_tier=SubscriptionTier.FREE, subscription_status=SubscriptionStatus.ACTIVE,
        created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
    )


def _mk_campaign(owner, tenant, code, name):
    return Campaign(
        campaign_id=uuid.uuid4(), tenant_id=tenant, client_id=owner.client_id,
        campaign_code=code, name=name, campaign_type=CampaignType.OOH_ADVERTISING,
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        status=CampaignStatus.ACTIVE,
        created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
    )


class World:
    """owner + same-tenant sibling + foreign-tenant client, and a POPULATED campaign."""
    pass


@pytest_asyncio.fixture
async def world():
    w = World()
    w.campaign_name = f"SECRET-CAMPAIGN-{uuid.uuid4().hex[:8]}"
    w.code = f"H3-{uuid.uuid4().hex[:8].upper()}"
    w.missing_code = f"H3-NOPE-{uuid.uuid4().hex[:8].upper()}"
    w.s3_keys = []
    async with _Sessions() as s:
        w.owner = _mk_client(DEFAULT_TENANT_ID, "owner")
        w.sibling = _mk_client(DEFAULT_TENANT_ID, "sibling")
        w.foreign = _mk_client(OTHER_TENANT_ID, "foreign")
        s.add_all([w.owner, w.sibling, w.foreign])
        await s.flush()
        w.vendor = Vendor(
            vendor_id=uuid.uuid4().hex[:6].upper(), tenant_id=DEFAULT_TENANT_ID,
            created_by_client_id=w.owner.client_id, name="H3 Vendor",
            phone_number="+919000000000", status=VendorStatus.ACTIVE,
            created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
        )
        s.add(w.vendor)
        w.campaign = _mk_campaign(w.owner, DEFAULT_TENANT_ID, w.code, w.campaign_name)
        s.add(w.campaign)
        await s.flush()
        for i in range(2):
            key = f"SECRET-STORAGE-KEY-{uuid.uuid4().hex[:10]}"
            w.s3_keys.append(key)
            p = Photo(
                photo_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID,
                campaign_id=w.campaign.campaign_id, vendor_id=w.vendor.vendor_id,
                capture_timestamp=datetime.now(tz=timezone.utc), s3_key=key,
                verification_status=VerificationStatus.VERIFIED,
                created_at=datetime.now(tz=timezone.utc),
            )
            s.add(p)
            await s.flush()
            s.add(SensorData(
                sensor_data_id=uuid.uuid4(), photo_id=p.photo_id,
                gps_latitude=LAT, gps_longitude=LON, gps_accuracy=5.0,
                schema_version="2.0", created_at=datetime.now(tz=timezone.utc),
            ))
        await s.commit()
    w.campaign_id = w.campaign.campaign_id
    yield w
    async with _Sessions() as s:
        await s.execute(delete(Campaign).where(Campaign.campaign_id == w.campaign_id))  # photos cascade
        await s.execute(delete(Vendor).where(Vendor.vendor_id == w.vendor.vendor_id))
        await s.execute(delete(Client).where(Client.client_id.in_(
            [w.owner.client_id, w.sibling.client_id, w.foreign.client_id])))
        await s.commit()


def _report_paths(code):
    return [
        f"/api/reports/campaigns/{code}/csv",
        f"/api/reports/campaigns/{code}/geojson",
        f"/api/reports/campaigns/{code}/statistics",
        f"/api/reports/campaigns/{code}/dashboard",
        f"/api/reports/campaigns/{code}/charts/verification?format=json",
        f"/api/reports/campaigns/{code}/charts/confidence?format=json",
        f"/api/reports/campaigns/{code}/charts/timeline?format=json",
        f"/api/reports/campaigns/{code}/pdf",
    ]


def _leak_tokens(w):
    return [LAT_S, LON_S, w.campaign_name, w.vendor.vendor_id, str(w.campaign_id), *w.s3_keys]


# --------------------------------------------------------------------------- #
# 1. Owner: access permitted, contract unchanged
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_owner_can_read_populated_campaign_reports(api_client, world):
    w = world
    h = _headers(w.owner)

    r = await api_client.get(f"/api/reports/campaigns/{w.code}/csv", headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert LAT_S in r.text and LON_S in r.text and w.s3_keys[0] in r.text

    r = await api_client.get(f"/api/reports/campaigns/{w.code}/geojson", headers=h)
    assert r.status_code == 200, r.text
    assert LAT_S in r.text and LON_S in r.text

    r = await api_client.get(f"/api/reports/campaigns/{w.code}/statistics", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["campaign"]["code"] == w.code
    assert body["statistics"]["total_photos"] == 2

    r = await api_client.get(f"/api/reports/campaigns/{w.code}/dashboard", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["statistics"]["statistics"]["total_photos"] == 2

    for chart in ("verification", "confidence"):
        r = await api_client.get(f"/api/reports/campaigns/{w.code}/charts/{chart}?format=json", headers=h)
        assert r.status_code == 200, (chart, r.text)
    # KNOWN PRE-EXISTING DEFECT (out of scope for Hotfix 3): the timeline chart 500s for the
    # owner on the baseline ("'str' object has no attribute 'date'"). This test only asserts
    # that the owner is NOT denied by authorization.
    r = await api_client.get(f"/api/reports/campaigns/{w.code}/charts/timeline?format=json", headers=h)
    assert r.status_code not in (401, 403, 404), r.text

    r = await api_client.get(f"/api/reports/campaigns/{w.code}/pdf", headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_owner_can_read_campaign_photos(api_client, world):
    w = world
    r = await api_client.get(f"/api/campaigns/{w.campaign_id}/photos", headers=_headers(w.owner))
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 2
    assert {row["campaign_id"] for row in rows} == {str(w.campaign_id)}


# --------------------------------------------------------------------------- #
# 2. Same-tenant NON-owner and foreign-tenant callers: 404 on every endpoint
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
@pytest.mark.parametrize("who", ["sibling", "foreign"])
async def test_non_owner_gets_404_on_every_report_endpoint(api_client, world, who):
    w = world
    caller = getattr(w, who)
    for path in _report_paths(w.code):
        r = await api_client.get(path, headers=_headers(caller))
        assert r.status_code == 404, f"{who} got {r.status_code} on {path}"


@pytest.mark.asyncio
@pytest.mark.parametrize("who", ["sibling", "foreign"])
async def test_non_owner_gets_404_on_campaign_photos(api_client, world, who):
    w = world
    r = await api_client.get(f"/api/campaigns/{w.campaign_id}/photos", headers=_headers(getattr(w, who)))
    assert r.status_code == 404, f"{who} got {r.status_code}: {r.text[:200]}"


# --------------------------------------------------------------------------- #
# 3. Unauthorized callers receive NO records / GPS / storage references / names
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
@pytest.mark.parametrize("who", ["sibling", "foreign"])
async def test_unauthorized_responses_leak_nothing(api_client, world, who):
    w = world
    caller = getattr(w, who)
    paths = _report_paths(w.code) + [f"/api/campaigns/{w.campaign_id}/photos"]
    for path in paths:
        r = await api_client.get(path, headers=_headers(caller))
        body = r.text
        for token in _leak_tokens(w):
            # the requested code itself is echoed in the 404 detail by design; skip only that token
            assert token not in body.replace(w.code, "<code>"), \
                f"{who}: {path} leaked {token!r}"


# --------------------------------------------------------------------------- #
# 4. Non-disclosure: unauthorized == nonexistent (same status, same body shape)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_unauthorized_404_identical_to_nonexistent_404(api_client, world):
    w = world
    for caller in (w.sibling, w.foreign):
        for tmpl in ("/api/reports/campaigns/{c}/csv", "/api/reports/campaigns/{c}/geojson",
                     "/api/reports/campaigns/{c}/statistics", "/api/reports/campaigns/{c}/dashboard"):
            real = await api_client.get(tmpl.format(c=w.code), headers=_headers(caller))
            gone = await api_client.get(tmpl.format(c=w.missing_code), headers=_headers(caller))
            assert real.status_code == gone.status_code == 404
            assert real.text.replace(w.code, "<c>") == gone.text.replace(w.missing_code, "<c>")
    # campaign photos: detail has no code, so bodies must be byte-identical
    for caller in (w.sibling, w.foreign):
        real = await api_client.get(f"/api/campaigns/{w.campaign_id}/photos", headers=_headers(caller))
        gone = await api_client.get(f"/api/campaigns/{uuid.uuid4()}/photos", headers=_headers(caller))
        assert real.status_code == gone.status_code == 404
        assert real.text == gone.text


# --------------------------------------------------------------------------- #
# 5. BOTH conditions are required: client_id AND tenant_id
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_owner_denied_when_campaign_tenant_is_inconsistent(api_client, world):
    """client_id matches but the campaign is stamped with another tenant (inconsistent
    record): ownership must fail closed for reports and campaign photos."""
    w = world
    code = f"H3-INC-{uuid.uuid4().hex[:8].upper()}"
    async with _Sessions() as s:
        inc = _mk_campaign(w.owner, OTHER_TENANT_ID, code, "inconsistent")
        s.add(inc)
        await s.commit()
        inc_id = inc.campaign_id
    try:
        for path in (f"/api/reports/campaigns/{code}/csv",
                     f"/api/reports/campaigns/{code}/statistics",
                     f"/api/campaigns/{inc_id}/photos"):
            r = await api_client.get(path, headers=_headers(w.owner))
            assert r.status_code == 404, f"owner got {r.status_code} on inconsistent campaign {path}"
    finally:
        async with _Sessions() as s:
            await s.execute(delete(Campaign).where(Campaign.campaign_id == inc_id))
            await s.commit()


# --------------------------------------------------------------------------- #
# 6. Every ReportGenerator entry point fails closed without an ownership scope
# --------------------------------------------------------------------------- #
def _gen(s, **scope):
    return ReportGenerator(s, ChartGenerator(), MapGenerator(), **scope)


@pytest.mark.asyncio
async def test_generator_methods_fail_closed_without_scope(world):
    w = world
    async with _Sessions() as s:
        for scope in ({}, {"tenant_id": DEFAULT_TENANT_ID}):     # unscoped, or tenant-only (old behaviour)
            g = _gen(s, **scope)
            for call in (g.generate_csv_report, g.generate_geojson_report, g.get_campaign_statistics):
                with pytest.raises(ValueError):
                    await call(w.code)
            with pytest.raises(ValueError):
                await g.generate_chart_data(w.code, "verification", "json")


@pytest.mark.asyncio
async def test_generator_methods_enforce_owner_and_tenant(world):
    w = world
    async with _Sessions() as s:
        wrong = [
            dict(tenant_id=DEFAULT_TENANT_ID, client_id=w.sibling.client_id),   # same tenant, non-owner
            dict(tenant_id=OTHER_TENANT_ID,  client_id=w.owner.client_id),      # owner id, wrong tenant
            dict(tenant_id=OTHER_TENANT_ID,  client_id=w.foreign.client_id),    # foreign
        ]
        for scope in wrong:
            g = _gen(s, **scope)
            for call in (g.generate_csv_report, g.generate_geojson_report, g.get_campaign_statistics):
                with pytest.raises(ValueError):
                    await call(w.code)
        ok = _gen(s, tenant_id=DEFAULT_TENANT_ID, client_id=w.owner.client_id)
        assert LAT_S in await ok.generate_csv_report(w.code)
        assert (await ok.get_campaign_statistics(w.code))["statistics"]["total_photos"] == 2


@pytest.mark.asyncio
async def test_generate_pdf_queue_handler_fails_closed(world):
    """The background handler builds its own ReportGenerator from a task payload; it
    must not be an unscoped route to campaign data."""
    from app.services.queue.handlers.pdf_handler import handle_generate_pdf
    w = world
    async with _Sessions() as s:
        # legacy payload shape (tenant only) and a foreign / sibling client must fail closed
        for payload in (
            {"campaign_code": w.code, "tenant_id": str(DEFAULT_TENANT_ID)},
            {"campaign_code": w.code, "tenant_id": str(DEFAULT_TENANT_ID), "client_id": str(w.sibling.client_id)},
            {"campaign_code": w.code, "tenant_id": str(OTHER_TENANT_ID), "client_id": str(w.foreign.client_id)},
        ):
            with pytest.raises(ValueError):
                await handle_generate_pdf(s, payload)
        # the owner's payload passes the ownership lookup (must not raise "not found")
        try:
            await handle_generate_pdf(s, {"campaign_code": w.code, "tenant_id": str(DEFAULT_TENANT_ID),
                                          "client_id": str(w.owner.client_id)})
        except ValueError as e:                                   # pragma: no cover
            pytest.fail(f"owner payload wrongly rejected: {e}")
        except Exception:
            pass  # unrelated PDF-rendering errors are out of scope here
