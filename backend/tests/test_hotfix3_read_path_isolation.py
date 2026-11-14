"""
Hotfix 3 (final read-path hardening) — legacy `photos` rows on client-facing reads.

A client may see a Photo row only if ALL of these hold:
    Campaign.client_id == client.client_id
    Campaign.tenant_id == client.tenant_id
    Photo.tenant_id    == client.tenant_id
and the Photo belongs to one of those campaigns.

Fixture data (disposable test DB):
  * 2 authorized photos      : owner's campaign, owner's tenant, vendor V
  * 1 foreign-tenant photo   : linked to the owner's campaign, carries another tenant id
  * 1 other-client photo     : sibling client's campaign, taken by vendor V, which is
                               ACTIVELY associated with BOTH clients (many-to-many model)

Endpoints under test (all client-authenticated):
  /api/reports/{export/csv, export/pdf, table-data, statistics, campaigns, time-series, vendors}
  /api/photos, /api/photos/locations
"""
import csv as _csv
import io as _io
import sys
import types
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

# Reuse the self-contained harness/fixtures of the reviewed Hotfix 3 test module.
from tests.test_hotfix3_campaign_report_authz import (  # noqa: F401  (fixtures + helpers)
    api_client, world, world_with_foreign_photo, _ensure_other_tenant, _stub_pdf_renderer,
    _headers, _foreign_tokens, _mk_campaign, _Sessions, hotfix_runtime_env,
    Photo, SensorData, VerificationStatus, Campaign, create_access_token,
    OTHER_TENANT_ID, DEFAULT_TENANT_ID, LAT_S, LON_S,
)
from app.models.vendor_client_association import VendorClientAssociation, AssociationStatus


# --------------------------------------------------------------------------- #
# World: adds the "vendor shared by two clients" photo + associations
# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def world_full(world_with_foreign_photo):
    w = world_with_foreign_photo
    w.sib_code = f"H3-SIB-{uuid.uuid4().hex[:8].upper()}"
    w.sib_name = f"SIBLING-CAMPAIGN-{uuid.uuid4().hex[:6]}"
    w.sib_lat_s, w.sib_lon_s = "8.46875", "76.28125"            # exact in the column's float precision
    w.sib_s3_key = f"SIBLING-KEY-{uuid.uuid4().hex[:10]}"
    assoc_ids = []
    async with _Sessions() as s:
        for c in (w.owner, w.sibling):                          # ONE vendor, associated with BOTH clients
            a = VendorClientAssociation(
                association_id=uuid.uuid4(), vendor_id=w.vendor.vendor_id, client_id=c.client_id,
                tenant_id=DEFAULT_TENANT_ID, status=AssociationStatus.ACTIVE,
                enrolled_at=datetime.now(tz=timezone.utc),
            )
            s.add(a)
            assoc_ids.append(a.association_id)
        sib = _mk_campaign(w.sibling, DEFAULT_TENANT_ID, w.sib_code, w.sib_name)
        s.add(sib)
        await s.flush()
        p = Photo(
            photo_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID, campaign_id=sib.campaign_id,
            vendor_id=w.vendor.vendor_id, capture_timestamp=datetime.now(tz=timezone.utc),
            s3_key=w.sib_s3_key, verification_status=VerificationStatus.VERIFIED,
            created_at=datetime.now(tz=timezone.utc),
        )
        s.add(p)
        await s.flush()
        s.add(SensorData(
            sensor_data_id=uuid.uuid4(), photo_id=p.photo_id,
            gps_latitude=8.46875, gps_longitude=76.28125, gps_accuracy=5.0,
            schema_version="2.0", created_at=datetime.now(tz=timezone.utc),
        ))
        await s.commit()
        w.sib_campaign_id, w.sib_photo_id = sib.campaign_id, p.photo_id
    async with _Sessions() as s:
        ids = (await s.execute(select(Photo.photo_id).where(Photo.s3_key.in_(w.s3_keys)))).scalars().all()
    w.auth_ids = {str(i) for i in ids}
    assert len(w.auth_ids) == 2
    yield w
    async with _Sessions() as s:
        await s.execute(delete(Campaign).where(Campaign.campaign_id == w.sib_campaign_id))   # photo cascades
        await s.execute(delete(VendorClientAssociation).where(
            VendorClientAssociation.association_id.in_(assoc_ids)))
        await s.commit()


def _excluded_tokens(w):
    """Everything that belongs to the foreign-tenant photo or to the other client's campaign."""
    return [*_foreign_tokens(w), w.sib_lat_s, w.sib_lon_s, w.sib_code, w.sib_name,
            w.sib_s3_key, str(w.sib_photo_id)]


def _assert_no_excluded(label, text, w):
    for token in _excluded_tokens(w):
        assert token not in text, f"{label} exposed {token!r}"


def _rows(body):
    if isinstance(body, list):
        return body
    for key in ("rows", "data", "photos"):
        if key in body:
            return body[key]
    raise AssertionError(f"unexpected body shape: {list(body)[:5]}")


async def _get(api, path, who):
    r = await api.get(path, headers=_headers(who))
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"
    return r


# --------------------------------------------------------------------------- #
# Row-level endpoints
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_export_csv_contains_only_authorized_photos(api_client, world_full):
    w = world_full
    r = await _get(api_client, "/api/reports/export/csv", w.owner)
    rows = list(_csv.reader(_io.StringIO(r.text)))
    header, data = rows[0], rows[1:]
    assert header[0] == "photo_id"
    assert {row[0] for row in data} == w.auth_ids and len(data) == 2
    _assert_no_excluded("export/csv", r.text, w)


@pytest.mark.asyncio
async def test_table_data_contains_only_authorized_photos(api_client, world_full):
    w = world_full
    r = await _get(api_client, "/api/reports/table-data", w.owner)
    ids = {row["photo_id"] for row in _rows(r.json())}
    assert ids == w.auth_ids
    _assert_no_excluded("table-data", r.text, w)


@pytest.mark.asyncio
async def test_legacy_photo_list_contains_only_authorized_photos(api_client, world_full):
    w = world_full
    r = await _get(api_client, "/api/photos?limit=200", w.owner)
    ids = {row["photo_id"] for row in r.json()}
    assert ids == w.auth_ids
    assert all(k in r.text for k in w.s3_keys)                  # valid photos stay visible (URLs carry the key)
    _assert_no_excluded("photos list", r.text, w)


@pytest.mark.asyncio
async def test_photo_map_contains_only_authorized_photos(api_client, world_full):
    w = world_full
    r = await _get(api_client, "/api/photos/locations", w.owner)
    ids = {f["properties"]["photo_id"] for f in r.json()["features"]}
    assert ids == w.auth_ids
    assert LAT_S in r.text and LON_S in r.text
    _assert_no_excluded("photos/locations", r.text, w)


# --------------------------------------------------------------------------- #
# Aggregate endpoints: totals must equal the authorized underlying records
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_aggregates_count_only_authorized_photos(api_client, world_full):
    w = world_full
    st = (await _get(api_client, "/api/reports/statistics", w.owner)).json()
    assert st["total_photos"] == 2 and st["verified_photos"] == 2
    assert st["failed_photos"] == 0 and st["pending_photos"] == 0

    camps = (await _get(api_client, "/api/reports/campaigns", w.owner)).json()
    mine = [c for c in camps if c["campaign_code"] == w.code]
    assert len(mine) == 1 and mine[0]["photo_count"] == 2 and mine[0]["verified_count"] == 2
    assert w.sib_code not in {c["campaign_code"] for c in camps}     # other client's campaign never listed

    ts = (await _get(api_client, "/api/reports/time-series", w.owner)).json()
    assert sum(x["count"] for x in ts) == 2


@pytest.mark.asyncio
async def test_vendor_statistics_count_only_the_requesting_clients_campaign_photos(api_client, world_full):
    """Vendor V is associated with BOTH clients and has photos in both clients' campaigns.
    Each client's vendor statistics must count only photos in ITS OWN campaigns."""
    w = world_full
    owner_view = (await _get(api_client, "/api/reports/vendors", w.owner)).json()
    ov = [v for v in owner_view if v["vendor_id"] == w.vendor.vendor_id]
    assert len(ov) == 1
    assert ov[0]["photo_count"] == 2 and ov[0]["verified_count"] == 2 and ov[0]["verification_rate"] == 1

    sibling_view = (await _get(api_client, "/api/reports/vendors", w.sibling)).json()
    sv = [v for v in sibling_view if v["vendor_id"] == w.vendor.vendor_id]
    assert len(sv) == 1
    assert sv[0]["photo_count"] == 1 and sv[0]["verified_count"] == 1     # only the sibling's own campaign photo

    # the foreign-tenant vendor must not appear for either client
    assert w.foreign_vendor_id not in {v["vendor_id"] for v in owner_view + sibling_view}


@pytest.mark.asyncio
async def test_every_read_path_agrees_on_the_authorized_set(api_client, world_full):
    """Cross-surface consistency: lists and aggregates all describe the same two photos."""
    w = world_full
    csv_ids = {r[0] for r in list(_csv.reader(_io.StringIO(
        (await _get(api_client, "/api/reports/export/csv", w.owner)).text)))[1:]}
    table_ids = {r["photo_id"] for r in _rows((await _get(api_client, "/api/reports/table-data", w.owner)).json())}
    list_ids = {r["photo_id"] for r in (await _get(api_client, "/api/photos?limit=200", w.owner)).json()}
    map_ids = {f["properties"]["photo_id"] for f in
               (await _get(api_client, "/api/photos/locations", w.owner)).json()["features"]}
    assert csv_ids == table_ids == list_ids == map_ids == w.auth_ids

    n = len(w.auth_ids)
    assert (await _get(api_client, "/api/reports/statistics", w.owner)).json()["total_photos"] == n
    assert sum(x["count"] for x in (await _get(api_client, "/api/reports/time-series", w.owner)).json()) == n
    camps = (await _get(api_client, "/api/reports/campaigns", w.owner)).json()
    assert sum(c["photo_count"] for c in camps) == n
    vend = (await _get(api_client, "/api/reports/vendors", w.owner)).json()
    assert sum(v["photo_count"] for v in vend) == n


# --------------------------------------------------------------------------- #
# PDF export: query isolation with a recording renderer (+ real fpdf2 smoke test if installed)
# --------------------------------------------------------------------------- #
class _RecordingFPDF:
    """Stand-in for fpdf.FPDF that records every text cell the export renders."""
    texts = []

    def __init__(self, *a, **k):
        self.w, self.l_margin, self.r_margin = 297.0, 10.0, 10.0

    def get_x(self): return 10.0
    def get_y(self): return 10.0

    def cell(self, w=0, h=0, text="", *a, **k):
        if text == "" and "txt" in k:
            text = k["txt"]
        type(self).texts.append(str(text))

    def output(self, *a, **k): return b"%PDF-1.4 recording-stub"
    def __getattr__(self, name): return lambda *a, **k: None


@pytest.mark.asyncio
async def test_export_pdf_renders_only_authorized_photos(api_client, world_full, monkeypatch):
    w = world_full
    _RecordingFPDF.texts = []
    fake = types.ModuleType("fpdf")
    fake.FPDF = _RecordingFPDF
    monkeypatch.setitem(sys.modules, "fpdf", fake)

    r = await api_client.get("/api/reports/export/pdf", headers=_headers(w.owner))
    assert r.status_code == 200, r.text[:200]
    texts = _RecordingFPDF.texts
    joined = " | ".join(texts)

    def summary(label):                       # the value cell directly follows its label cell
        return texts[texts.index(label) + 1]

    assert summary("Total Photos") == "2" and summary("Verified") == "2"
    assert summary("Rejected") == "0" and summary("Pending") == "0"
    assert texts.count(w.campaign_name) == 2                    # one row per authorized photo
    assert texts.count("H3 Vendor") == 2                        # shared vendor: ONLY the owner's campaign rows
    assert w.sib_name not in joined and "H3 Foreign Vendor" not in joined
    assert "33.7578, 101.5078" not in joined and "8.4688, 76.2812" not in joined   # foreign / other-client GPS
    assert "12.3438, 77.7656" in joined                          # authorized GPS still rendered


@pytest.mark.asyncio
async def test_export_pdf_renders_with_real_fpdf_when_installed(api_client, world_full):
    pytest.importorskip("fpdf", reason="fpdf2 not installed in this environment; query isolation is covered "
                                       "by the recording-renderer test above")
    r = await api_client.get("/api/reports/export/pdf", headers=_headers(world_full.owner))
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


# --------------------------------------------------------------------------- #
# Inconsistent campaign tenant: BOTH campaign.client_id and campaign.tenant_id are required
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_campaign_with_inconsistent_tenant_is_excluded_from_all_read_paths(api_client, world_full):
    w = world_full
    code = f"H3-INC3-{uuid.uuid4().hex[:8].upper()}"
    lat_s, lon_s = "5.28125", "66.53125"
    async with _Sessions() as s:
        inc = _mk_campaign(w.owner, OTHER_TENANT_ID, code, "INCONSISTENT-CAMPAIGN")   # owner's id, other tenant
        s.add(inc)
        await s.flush()
        p = Photo(
            photo_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID, campaign_id=inc.campaign_id,   # photo tenant == client tenant
            vendor_id=w.vendor.vendor_id, capture_timestamp=datetime.now(tz=timezone.utc),
            s3_key=f"INC-KEY-{uuid.uuid4().hex[:8]}", verification_status=VerificationStatus.VERIFIED,
            created_at=datetime.now(tz=timezone.utc),
        )
        s.add(p)
        await s.flush()
        s.add(SensorData(sensor_data_id=uuid.uuid4(), photo_id=p.photo_id, gps_latitude=5.28125,
                         gps_longitude=66.53125, gps_accuracy=5.0, schema_version="2.0",
                         created_at=datetime.now(tz=timezone.utc)))
        await s.commit()
        inc_id, inc_photo = inc.campaign_id, str(p.photo_id)
    try:
        for path in ("/api/reports/export/csv", "/api/reports/table-data", "/api/photos?limit=200",
                     "/api/photos/locations", "/api/reports/campaigns", "/api/reports/vendors"):
            r = await _get(api_client, path, w.owner)
            for token in (inc_photo, code, "INCONSISTENT-CAMPAIGN", lat_s, lon_s):
                assert token not in r.text, f"{path} exposed {token!r}"
        assert (await _get(api_client, "/api/reports/statistics", w.owner)).json()["total_photos"] == 2
        assert sum(x["count"] for x in (await _get(api_client, "/api/reports/time-series", w.owner)).json()) == 2
    finally:
        async with _Sessions() as s:
            await s.execute(delete(Campaign).where(Campaign.campaign_id == inc_id))
            await s.commit()


# --------------------------------------------------------------------------- #
# NULL / missing scope fails closed; authentication class of endpoints unchanged
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_missing_scope_fails_closed_in_the_shared_predicate(world_full):
    from app.core.photo_visibility import photo_visibility_clause, owned_campaigns_subquery
    w = world_full
    good = SimpleNamespace(client_id=w.owner.client_id, tenant_id=DEFAULT_TENANT_ID)
    async with _Sessions() as s:
        total_photos = (await s.execute(select(func.count()).select_from(Photo))).scalar()
        assert total_photos >= 4                                   # data exists, so zero below is meaningful
        assert (await s.execute(select(func.count()).select_from(Photo).where(photo_visibility_clause(good)))).scalar() == 2
        for bad in (
            SimpleNamespace(client_id=None, tenant_id=DEFAULT_TENANT_ID),
            SimpleNamespace(client_id=w.owner.client_id, tenant_id=None),
            SimpleNamespace(client_id=None, tenant_id=None),
            None,
        ):
            n = (await s.execute(select(func.count()).select_from(Photo).where(photo_visibility_clause(bad)))).scalar()
            c = (await s.execute(owned_campaigns_subquery(bad))).all()
            assert n == 0 and c == [], f"scope {bad!r} must see nothing"


@pytest.mark.asyncio
async def test_client_endpoints_still_reject_vendor_tokens_and_vendor_endpoint_rejects_clients(api_client, world_full):
    w = world_full
    vendor_token = create_access_token({"sub": w.vendor.vendor_id, "type": "vendor", "vendor_id": w.vendor.vendor_id})
    vh = {"Authorization": f"Bearer {vendor_token}", "X-Tenant-ID": str(DEFAULT_TENANT_ID)}
    for path in ("/api/reports/export/csv", "/api/reports/export/pdf", "/api/reports/table-data",
                 "/api/reports/statistics", "/api/reports/campaigns", "/api/reports/time-series",
                 "/api/reports/vendors", "/api/photos", "/api/photos/locations"):
        r = await api_client.get(path, headers=vh)
        assert r.status_code == 403, f"{path} accepted a vendor token ({r.status_code})"
    # the vendor-authenticated single-photo endpoint is still vendor-only
    some_photo = next(iter(w.auth_ids))
    r = await api_client.get(f"/api/photos/{some_photo}", headers=_headers(w.owner))
    assert r.status_code == 403
