"""
Client-ownership authorization for the Evidence detail / distance / route-analysis reads.

Before: GET /api/evidence/{id}, /api/evidence/distance and /api/evidence/route-analysis
checked only ``Evidence.tenant_id == client.tenant_id`` (and ``Photo.tenant_id`` for the
route's legacy branch). Any client in the same tenant could read another client's
evidence, measure distances between its captures and pull a vendor's GPS route.

After: the same visibility rules as the Gallery / Map / Statistics surfaces apply:
  * campaign-bound Evidence  -> campaign owned by the client in its own tenant
                                 (Hotfix 3 rule) and evidence in the client's tenant;
  * campaign-free Quick Capture -> ACTIVE vendor-client association + four-way tenant
                                 agreement (Option A interim rule);
  * legacy photos in the route -> Hotfix 3 photo predicate;
  * missing client scope fails closed.
Unauthorized and nonexistent ids return the identical 404.

World (DEFAULT tenant unless noted):
  A  owns vendor V (ACTIVE assoc) and campaign CA          -> owner
  S  ACTIVE assoc with V, owns campaign CS                 -> shared-vendor client
  I  INACTIVE assoc with V                                 -> inactive association
  B  no association, no campaigns                          -> unrelated same-tenant client
  F  OTHER tenant                                          -> foreign tenant
  Evidence by V: e_ca (in CA), e_cs (in CS), q1, q2 (Quick Capture); legacy photo p_ca in CA.
"""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import delete

from tests.hotfix_support import hotfix_runtime_env  # noqa: F401
from tests.test_quick_capture_visibility import (  # noqa: F401
    _Sessions, OTHER_TENANT_ID, DEFAULT_TENANT_ID, api_client, seed, _ensure_other_tenant, _headers,
)
from tests.test_quick_capture_visibility_parity import _campaign, _evidence
from app.core.deps import get_current_client
from app.main import app
from app.models.campaign import Campaign
from app.models.photo import Photo, VerificationStatus
from app.models.sensor_data import SensorData
from app.models.vendor_client_association import AssociationStatus

NOW = datetime.now(tz=timezone.utc)


@pytest_asyncio.fixture
async def world(seed):
    w = SimpleNamespace()
    async with _Sessions() as s:
        w.A = await seed.client(s); w.S = await seed.client(s); w.I = await seed.client(s)
        w.B = await seed.client(s); w.F = await seed.client(s, tenant=OTHER_TENANT_ID)
        w.V = await seed.vendor(s, w.A)
        await seed.assoc(s, w.V, w.A, AssociationStatus.ACTIVE)
        await seed.assoc(s, w.V, w.S, AssociationStatus.ACTIVE)
        await seed.assoc(s, w.V, w.I, AssociationStatus.INACTIVE)
        ca, cs = _campaign(w.A, DEFAULT_TENANT_ID), _campaign(w.S, DEFAULT_TENANT_ID)
        s.add(ca); s.add(cs); await s.flush()
        w.campaign_ids = [ca.campaign_id, cs.campaign_id]
        e_ca = _evidence(w.V, ca.campaign_id, lat=19.00, lon=72.80)
        e_cs = _evidence(w.V, cs.campaign_id, lat=19.10, lon=72.85)
        q1 = _evidence(w.V, None, lat=19.20, lon=72.90)
        q2 = _evidence(w.V, None, lat=19.30, lon=72.95)
        for i, e in enumerate((e_ca, e_cs, q1, q2)):
            e.created_at = NOW + timedelta(minutes=i)
            s.add(e)
        p = Photo(
            photo_id=uuid.uuid4(), tenant_id=DEFAULT_TENANT_ID, campaign_id=ca.campaign_id,
            vendor_id=w.V.vendor_id, capture_timestamp=NOW, s3_key=f"ea-{uuid.uuid4().hex}",
            verification_status=VerificationStatus.VERIFIED, created_at=NOW + timedelta(minutes=5),
        )
        s.add(p); await s.flush()
        s.add(SensorData(sensor_data_id=uuid.uuid4(), photo_id=p.photo_id, gps_latitude=19.40,
                         gps_longitude=73.00, gps_accuracy=5.0, schema_version="2.0", created_at=NOW))
        await seed.finalize(s, e_ca, e_cs, q1, q2)
        w.p_ca = str(p.photo_id)
    w.e_ca, w.e_cs, w.q1, w.q2 = (str(e.evidence_id) for e in (e_ca, e_cs, q1, q2))
    yield w
    async with _Sessions() as s:
        await s.execute(delete(SensorData).where(SensorData.photo_id == uuid.UUID(w.p_ca)))
        await s.execute(delete(Photo).where(Photo.photo_id == uuid.UUID(w.p_ca)))
        await s.execute(delete(Campaign).where(Campaign.campaign_id.in_(w.campaign_ids)))
        await s.commit()


async def _detail(api, c, eid):
    return await api.get(f"/api/evidence/{eid}", headers=_headers(c))


async def _distance(api, c, a, b):
    return await api.get(f"/api/evidence/distance?id1={a}&id2={b}", headers=_headers(c))


async def _route_ids(api, c, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    r = await api.get(f"/api/evidence/route-analysis?{q}", headers=_headers(c))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_points"] == len(body["points"])
    return {p["id"] for p in body["points"]}


# ------------------------------------------------------------------ detail
@pytest.mark.asyncio
async def test_detail_visible_only_to_authorized_clients(api_client, world):
    w = world
    expected = {
        "A": {w.e_ca, w.q1, w.q2},      # owner: own campaign + Quick Capture
        "S": {w.e_cs, w.q1, w.q2},      # shared vendor: own campaign + Quick Capture, NOT A's campaign
        "I": set(), "B": set(), "F": set(),
    }
    for name, allowed in expected.items():
        c = getattr(w, name)
        for eid in (w.e_ca, w.e_cs, w.q1, w.q2):
            r = await _detail(api_client, c, eid)
            want = 200 if eid in allowed else 404
            assert r.status_code == want, f"client {name} evidence {eid[:8]}: {r.status_code} != {want}"


@pytest.mark.asyncio
async def test_detail_unauthorized_404_identical_to_nonexistent(api_client, world):
    w = world
    missing = await _detail(api_client, w.B, uuid.uuid4())
    assert missing.status_code == 404
    for c in (w.B, w.I, w.F):
        for eid in (w.e_ca, w.q1):
            r = await _detail(api_client, c, eid)
            assert r.status_code == 404 and r.content == missing.content


@pytest.mark.asyncio
async def test_detail_owner_response_contract_unchanged(api_client, world):
    r = await _detail(api_client, world.A, world.e_ca)
    assert r.status_code == 200
    assert set(r.json()) == {
        "evidence_id", "evidence_type", "campaign_id", "vendor_id", "category", "text_content",
        "file_url", "thumbnail_url", "file_size_bytes", "duration_seconds", "capture_timestamp",
        "latitude", "longitude", "accuracy", "verification_status", "verification_confidence",
        "verification_flags", "created_at",
    }


# ------------------------------------------------------------------ distance
@pytest.mark.asyncio
async def test_distance_requires_both_items_visible(api_client, world):
    w = world
    assert (await _distance(api_client, w.A, w.e_ca, w.q1)).status_code == 200
    assert (await _distance(api_client, w.S, w.q1, w.q2)).status_code == 200
    missing = await _distance(api_client, w.B, uuid.uuid4(), uuid.uuid4())
    assert missing.status_code == 404
    denied = [
        (w.B, w.e_ca, w.q1), (w.B, w.q1, w.q2),     # unrelated same-tenant client
        (w.I, w.q1, w.q2),                          # inactive association
        (w.F, w.e_ca, w.q1),                        # foreign tenant
        (w.S, w.e_ca, w.q1),                        # shared vendor, but e_ca is A's campaign
        (w.A, w.e_cs, w.q1),                        # owner, but e_cs is S's campaign
    ]
    for c, a, b in denied:
        r = await _distance(api_client, c, a, b)
        assert r.status_code == 404 and r.content == missing.content, (a[:8], b[:8], r.status_code, r.text)


# ------------------------------------------------------------------ route analysis
@pytest.mark.asyncio
async def test_route_by_vendor_returns_only_authorized_points(api_client, world):
    w = world
    v = w.V.vendor_id
    assert await _route_ids(api_client, w.A, vendor_id=v) == {w.e_ca, w.q1, w.q2, w.p_ca}
    assert await _route_ids(api_client, w.S, vendor_id=v) == {w.e_cs, w.q1, w.q2}
    for c in (w.B, w.I, w.F):
        assert await _route_ids(api_client, c, vendor_id=v) == set()


@pytest.mark.asyncio
async def test_route_by_foreign_campaign_returns_nothing(api_client, world):
    w = world
    ca = str(w.campaign_ids[0])
    assert await _route_ids(api_client, w.A, campaign_id=ca) == {w.e_ca, w.p_ca}
    for c in (w.S, w.B, w.I, w.F):
        assert await _route_ids(api_client, c, campaign_id=ca) == set()


# ------------------------------------------------------------------ missing scope
@pytest.mark.asyncio
@pytest.mark.parametrize("scope", [
    {"client_id": None, "tenant_id": DEFAULT_TENANT_ID},
    {"client_id": uuid.uuid4(), "tenant_id": None},
])
async def test_missing_client_scope_fails_closed(api_client, world, scope):
    w = world
    app.dependency_overrides[get_current_client] = lambda: SimpleNamespace(**scope)
    try:
        h = {"Authorization": "Bearer ignored"}
        r = await api_client.get(f"/api/evidence/{w.q1}", headers=h)
        assert r.status_code == 404, r.text
        r = await api_client.get(f"/api/evidence/distance?id1={w.q1}&id2={w.q2}", headers=h)
        assert r.status_code == 404, r.text
        r = await api_client.get(f"/api/evidence/route-analysis?vendor_id={w.V.vendor_id}", headers=h)
        assert r.status_code == 200 and r.json()["total_points"] == 0, r.text
    finally:
        app.dependency_overrides.pop(get_current_client, None)
