"""
Option A x Hotfix 3 parity tests for Evidence visibility.

Hotfix 3 made legacy ``photos`` reads require: the campaign is owned by the client
(``Campaign.client_id``), the campaign is stamped with the client's tenant
(``Campaign.tenant_id``), and the row carries the client's tenant; a missing scope
fails closed. Option A's Evidence predicate must apply the SAME campaign rule so the
Gallery, Map, Statistics and report-detail surfaces agree for legacy photos and
Evidence rows alike.

Also pins the multi-client vendor behaviour:
  * campaign-bound Evidence from a vendor shared by two clients is visible ONLY to
    the client that owns the campaign;
  * campaign-free Quick Capture from that vendor is visible to every client with an
    ACTIVE association (Option A interim rule, documented, unchanged here).
"""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select, func
from sqlalchemy.dialects import postgresql

from tests.hotfix_support import hotfix_runtime_env  # noqa: F401  (autouse: app-runtime DB + default tenant)
from tests.test_quick_capture_visibility import (  # noqa: F401  (fixtures)
    _Sessions, OTHER_TENANT_ID, DEFAULT_TENANT_ID, api_client, seed, _ensure_other_tenant,
    gallery_ids, map_ids, stats, table_ids,
)
from app.models.campaign import Campaign, CampaignType, CampaignStatus
from app.models.evidence import Evidence
from app.models.vendor_client_association import AssociationStatus


def _campaign(client, tenant):
    return Campaign(
        campaign_id=uuid.uuid4(), tenant_id=tenant, client_id=client.client_id,
        campaign_code=f"QP-{uuid.uuid4().hex[:8].upper()}", name="parity",
        campaign_type=CampaignType.OOH_ADVERTISING,
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        status=CampaignStatus.ACTIVE,
        created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
    )


def _evidence(vendor, campaign_id, tenant=DEFAULT_TENANT_ID, lat=19.2, lon=72.9):
    return Evidence(
        tenant_id=tenant, vendor_id=vendor.vendor_id, campaign_id=campaign_id,
        evidence_type="photo", verification_status="verified",
        latitude=lat, longitude=lon, file_url="https://example.invalid/p.jpg",
        created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
    )


async def _drop_campaigns(*ids):
    async with _Sessions() as s:
        await s.execute(delete(Campaign).where(Campaign.campaign_id.in_(ids)))
        await s.commit()


# 1. Campaign owned by the client but stamped with ANOTHER tenant (inconsistent data).
#    Hotfix 3 hides legacy photos in such a campaign; Evidence must be hidden too.
@pytest.mark.asyncio
async def test_inconsistent_campaign_tenant_evidence_hidden_on_all_surfaces(api_client, seed):
    async with _Sessions() as s:
        a = await seed.client(s)
        va = await seed.vendor(s, a)
        await seed.assoc(s, va, a, AssociationStatus.ACTIVE)
        bad = _campaign(a, OTHER_TENANT_ID)      # client_id = A, tenant_id = foreign
        good = _campaign(a, DEFAULT_TENANT_ID)
        s.add(bad); s.add(good)
        e_bad, e_good = _evidence(va, bad.campaign_id), _evidence(va, good.campaign_id)
        s.add(e_bad); s.add(e_good)
        await seed.finalize(s, e_bad, e_good)
        ids = (bad.campaign_id, good.campaign_id)
    b, g_ = str(e_bad.evidence_id), str(e_good.evidence_id)
    try:
        gal, mp, tb = await gallery_ids(api_client, a), await map_ids(api_client, a), await table_ids(api_client, a)
        assert b not in gal, "inconsistent-tenant campaign evidence leaked into Gallery"
        assert b not in mp, "inconsistent-tenant campaign evidence leaked into Map"
        assert b not in tb, "inconsistent-tenant campaign evidence leaked into report detail"
        assert g_ in gal and g_ in mp and g_ in tb, "legitimate campaign evidence must stay visible"
        st = await stats(api_client, a)
        assert st["total_photos"] == 1 and st["verified_photos"] == 1, st
    finally:
        await _drop_campaigns(*ids)


# 2. Missing scope fails closed in the shared Evidence predicate (parity with
#    app.core.photo_visibility), instead of relying on `== None` rendering IS NULL.
@pytest.mark.parametrize("client", [
    None,
    SimpleNamespace(client_id=None, tenant_id=DEFAULT_TENANT_ID),
    SimpleNamespace(client_id=uuid.uuid4(), tenant_id=None),
])
def test_missing_scope_fails_closed_in_evidence_predicate(client):
    from app.core.evidence_visibility import (
        evidence_visibility_clause, quick_capture_visibility_clause, campaign_bound_visibility_clause,
    )
    for fn in (evidence_visibility_clause, quick_capture_visibility_clause, campaign_bound_visibility_clause):
        sql = str(fn(client).compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        assert sql.strip().lower() == "false", f"{fn.__name__} must be FALSE without scope, got: {sql[:120]}"


# 3. Vendor ACTIVE with two same-tenant clients: campaign-bound evidence stays with
#    the campaign owner only; Quick Capture is visible to both (interim rule).
@pytest.mark.asyncio
async def test_shared_vendor_campaign_evidence_only_visible_to_campaign_owner(api_client, seed):
    async with _Sessions() as s:
        a = await seed.client(s); b = await seed.client(s)
        v = await seed.vendor(s, a)
        await seed.assoc(s, v, a, AssociationStatus.ACTIVE)
        await seed.assoc(s, v, b, AssociationStatus.ACTIVE)
        cam_a = _campaign(a, DEFAULT_TENANT_ID); s.add(cam_a)
        e_cam = _evidence(v, cam_a.campaign_id)
        e_qc = _evidence(v, None, lat=19.3, lon=72.7)
        s.add(e_cam); s.add(e_qc)
        await seed.finalize(s, e_cam, e_qc)
        cid = cam_a.campaign_id
    c_id, q_id = str(e_cam.evidence_id), str(e_qc.evidence_id)
    try:
        for surface in (gallery_ids, map_ids, table_ids):
            seen_a, seen_b = await surface(api_client, a), await surface(api_client, b)
            assert c_id in seen_a, f"owner lost campaign evidence on {surface.__name__}"
            assert c_id not in seen_b, f"campaign evidence leaked to non-owner on {surface.__name__}"
            assert q_id in seen_a and q_id in seen_b, f"Quick Capture interim rule broken on {surface.__name__}"
        sa, sb = await stats(api_client, a), await stats(api_client, b)
        assert sa["total_photos"] == 2, sa
        assert sb["total_photos"] == 1, sb
    finally:
        await _drop_campaigns(cid)


# 4. Deactivating one association removes Quick Capture for that client only;
#    the campaign owner keeps its campaign evidence.
@pytest.mark.asyncio
async def test_shared_vendor_inactive_second_client_sees_nothing(api_client, seed):
    async with _Sessions() as s:
        a = await seed.client(s); b = await seed.client(s)
        v = await seed.vendor(s, a)
        await seed.assoc(s, v, a, AssociationStatus.ACTIVE)
        await seed.assoc(s, v, b, AssociationStatus.INACTIVE)
        cam_a = _campaign(a, DEFAULT_TENANT_ID); s.add(cam_a)
        e_cam = _evidence(v, cam_a.campaign_id); e_qc = _evidence(v, None, lat=19.4, lon=72.6)
        s.add(e_cam); s.add(e_qc)
        await seed.finalize(s, e_cam, e_qc)
        cid = cam_a.campaign_id
    try:
        for surface in (gallery_ids, map_ids, table_ids):
            seen_b = await surface(api_client, b)
            assert str(e_cam.evidence_id) not in seen_b and str(e_qc.evidence_id) not in seen_b, surface.__name__
        assert (await stats(api_client, b))["total_photos"] == 0
    finally:
        await _drop_campaigns(cid)


# 5. Predicate parity: Evidence campaign rule equals the Hotfix 3 owned-campaigns rule.
@pytest.mark.asyncio
async def test_evidence_campaign_rule_matches_hotfix3_owned_campaigns(seed):
    from app.core.evidence_visibility import client_campaign_ids_subquery
    from app.core.photo_visibility import owned_campaigns_subquery
    async with _Sessions() as s:
        a = await seed.client(s)
        c1 = _campaign(a, DEFAULT_TENANT_ID); c2 = _campaign(a, OTHER_TENANT_ID)
        s.add(c1); s.add(c2); await s.commit()
        ev = set((await s.execute(client_campaign_ids_subquery(a))).scalars())
        h3 = set((await s.execute(owned_campaigns_subquery(a))).scalars())
    try:
        assert ev == h3 == {c1.campaign_id}, (ev, h3)
    finally:
        await _drop_campaigns(c1.campaign_id, c2.campaign_id)
