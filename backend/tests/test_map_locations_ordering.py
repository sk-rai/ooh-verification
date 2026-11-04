"""Phase C — Task 6: deterministic ordering + bounded-completeness for the map.

Spec: .kiro/specs/map-tracking-isolation-fix (Task 6, Property 1)

Verifies, for GET /api/photos/locations, that BOTH the legacy (photos+sensor_data)
and evidence sources are ordered newest-first (capture_timestamp DESC) with NULLS
LAST and a stable id tie-break (photo_id / evidence_id DESC), applied BEFORE the
documented per-source LIMIT 500 bound. "Bounded completeness" means: the response
contains every qualifying row up to the 500-per-source limit; if a source has more
than 500 located rows, the 500 newest by this order are returned.

Note: Photo.capture_timestamp is NOT NULL in the schema, so the NULL-timestamp /
NULLS LAST case can only be exercised on the evidence path (Evidence.capture_timestamp
is nullable). The id tie-break (two rows with the IDENTICAL timestamp) is exercised
on both paths.

The bound test exercises the REAL production limit: it seeds 520 located evidence
rows for one client (one batch insert) and calls the unmodified endpoint, asserting
exactly 500 features come back and that they are the 500 newest. There is no
test-only limit override or alternate code path.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.hotfix_support import hotfix_runtime_env  # noqa: F401  (autouse runtime env)
from tests.test_map_locations_isolation import (  # noqa: F401
    api_client, seeder, _headers, TestSessionLocal,
)
from app.models.evidence import Evidence


@pytest.mark.asyncio
async def test_evidence_ordering_newest_first_nulls_last_with_id_tiebreak(api_client, seeder):
    """Evidence features are ordered by capture_timestamp DESC, NULLS LAST, then
    evidence_id DESC for ties (including a NULL-timestamp row and two rows sharing
    the SAME timestamp)."""
    async with TestSessionLocal() as s:
        c = await seeder.client(s, f"ord_{uuid.uuid4().hex[:8]}@x.com", "Order Co")
        cam = await seeder.campaign(s, c)
        v = await seeder.vendor(s, c)

        base = datetime(2026, 6, 1, tzinfo=timezone.utc)
        e_old = await seeder.evidence(s, cam, v, 19.01, 72.81, "verified")
        e_old.capture_timestamp = base
        e_new = await seeder.evidence(s, cam, v, 19.02, 72.82, "verified")
        e_new.capture_timestamp = base + timedelta(days=10)
        # Tie: two rows at the SAME timestamp -> ordered by evidence_id DESC.
        e_tie1 = await seeder.evidence(s, cam, v, 19.03, 72.83, "verified")
        e_tie1.capture_timestamp = base + timedelta(days=5)
        e_tie2 = await seeder.evidence(s, cam, v, 19.04, 72.84, "verified")
        e_tie2.capture_timestamp = base + timedelta(days=5)
        # NULL capture_timestamp -> must sort LAST regardless of how old/new others are.
        e_null = await seeder.evidence(s, cam, v, 19.05, 72.85, "verified")
        e_null.capture_timestamp = None
        await s.commit()

    resp = await api_client.get("/api/photos/locations", headers=_headers(c))
    assert resp.status_code == 200, resp.text
    ids_in_order = [f["properties"]["photo_id"] for f in resp.json()["features"]]

    tie_first, tie_second = sorted([e_tie1.evidence_id, e_tie2.evidence_id], reverse=True)
    expected = [
        str(e_new.evidence_id),      # newest timestamp
        str(tie_first),              # tie, higher id first
        str(tie_second),             # tie, lower id second
        str(e_old.evidence_id),      # oldest timestamp
        str(e_null.evidence_id),     # NULL timestamp sorts LAST
    ]
    assert ids_in_order == expected, f"got {ids_in_order}"


@pytest.mark.asyncio
async def test_legacy_ordering_newest_first_with_id_tiebreak(api_client, seeder):
    """Legacy features are ordered by capture_timestamp DESC, then photo_id DESC
    for ties. (capture_timestamp is NOT NULL on Photo, so no NULLS-LAST case here.)
    """
    async with TestSessionLocal() as s:
        c = await seeder.client(s, f"lord_{uuid.uuid4().hex[:8]}@x.com", "Legacy Order Co")
        cam = await seeder.campaign(s, c)
        v = await seeder.vendor(s, c)

        base = datetime(2026, 6, 1, tzinfo=timezone.utc)

        # Reuse the seeder's legacy_photo helper, then override capture_timestamp
        # so we control the exact ordering.
        p_old = await seeder.legacy_photo(s, cam, v, 19.11, 72.91)
        p_old.capture_timestamp = base
        p_new = await seeder.legacy_photo(s, cam, v, 19.12, 72.92)
        p_new.capture_timestamp = base + timedelta(days=10)
        p_tie1 = await seeder.legacy_photo(s, cam, v, 19.13, 72.93)
        p_tie1.capture_timestamp = base + timedelta(days=5)
        p_tie2 = await seeder.legacy_photo(s, cam, v, 19.14, 72.94)
        p_tie2.capture_timestamp = base + timedelta(days=5)
        await s.commit()

    resp = await api_client.get("/api/photos/locations", headers=_headers(c))
    assert resp.status_code == 200, resp.text
    ids_in_order = [f["properties"]["photo_id"] for f in resp.json()["features"]]

    tie_first, tie_second = sorted([p_tie1.photo_id, p_tie2.photo_id], reverse=True)
    expected = [str(p_new.photo_id), str(tie_first), str(tie_second), str(p_old.photo_id)]
    assert ids_in_order == expected, f"got {ids_in_order}"


@pytest.mark.asyncio
async def test_combined_response_includes_both_sources(api_client, seeder):
    """When a client has BOTH legacy and evidence located rows, the response
    includes features from both sources (union, not either/or)."""
    async with TestSessionLocal() as s:
        c = await seeder.client(s, f"both_{uuid.uuid4().hex[:8]}@x.com", "Both Co")
        cam = await seeder.campaign(s, c)
        v = await seeder.vendor(s, c)
        ev = await seeder.evidence(s, cam, v, 19.21, 72.95, "verified")
        ph = await seeder.legacy_photo(s, cam, v, 19.22, 72.96)
        await s.commit()

    resp = await api_client.get("/api/photos/locations", headers=_headers(c))
    assert resp.status_code == 200, resp.text
    ids = {f["properties"]["photo_id"] for f in resp.json()["features"]}
    assert str(ev.evidence_id) in ids
    assert str(ph.photo_id) in ids


@pytest.mark.asyncio
async def test_bounded_completeness_500_per_source_newest_kept(api_client, seeder):
    """Bounded completeness: with MORE than 500 located evidence rows for one
    client, exactly 500 evidence features are returned, and they are the 500
    NEWEST by capture_timestamp (none of the oldest rows leak through). Uses the
    PRODUCTION query unmodified (no test-only limit override) with a seeded batch
    of 520 rows so the real 500-row bound is exercised end-to-end.
    """
    async with TestSessionLocal() as s:
        c = await seeder.client(s, f"bnd_{uuid.uuid4().hex[:8]}@x.com", "Bound Co")
        cam = await seeder.campaign(s, c)
        v = await seeder.vendor(s, c)

        total = 520
        base = datetime(2020, 1, 1, tzinfo=timezone.utc)
        rows = []
        for i in range(total):
            eid = uuid.uuid4()
            rows.append(Evidence(
                evidence_id=eid, tenant_id=cam.tenant_id, campaign_id=cam.campaign_id,
                vendor_id=v.vendor_id, evidence_type="photo",
                latitude=10.0 + (i % 100) * 0.001, longitude=20.0 + (i % 100) * 0.001,
                verification_status="verified", verification_confidence=0.9,
                verification_flags=[], file_url="https://res.cloudinary.com/demo/b.jpg",
                thumbnail_url=None, file_hash="b" * 64,
                capture_timestamp=base + timedelta(minutes=i),  # strictly increasing -> newest = last i
                created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
            ))
            seeder.evidence_ids.append(eid)
        s.add_all(rows)
        await s.commit()
        newest_500_ids = {str(r.evidence_id) for r in sorted(rows, key=lambda r: r.capture_timestamp, reverse=True)[:500]}
        oldest_20_ids = {str(r.evidence_id) for r in sorted(rows, key=lambda r: r.capture_timestamp)[:20]}

    resp = await api_client.get("/api/photos/locations", headers=_headers(c))
    assert resp.status_code == 200, resp.text
    feats = resp.json()["features"]
    returned_ids = {f["properties"]["photo_id"] for f in feats}

    assert len(feats) == 500, f"expected exactly the 500-per-source bound, got {len(feats)}"
    assert returned_ids == newest_500_ids, "the 500 returned must be exactly the 500 newest"
    assert returned_ids.isdisjoint(oldest_20_ids), "none of the oldest rows may leak through the bound"
