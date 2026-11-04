"""Phase C — Task 7: evidence feature-mapping tests for GET /api/photos/locations.

Spec: .kiro/specs/map-tracking-isolation-fix (Task 7, Property 1)

Pins the exact mapping from an Evidence row to a GeoJSON feature's properties:
  - status: all four verification_status values (verified/pending/flagged/rejected)
  - confidence: verification_confidence (or 0 when NULL)
  - flags: verification_flags (or [] when NULL)
  - photo_url: evidence.file_url directly (NOT a storage-service-resolved key)
  - thumbnail_url: evidence.thumbnail_url, including the NULL case (non-photo
    evidence, e.g. a voice_note / text_note / video with no thumbnail)
  - captured_at: capture_timestamp, falling back to created_at when NULL
  - geometry: [longitude, latitude] in that order

Invalid-coordinate exclusion is covered in test_map_locations_evidence_coordinates.py
(Phase B); this module focuses on property-mapping fidelity for VALID rows only.
"""
import uuid
from datetime import datetime, timezone

import pytest

from tests.hotfix_support import hotfix_runtime_env  # noqa: F401  (autouse runtime env)
from tests.test_map_locations_isolation import (  # noqa: F401
    api_client, seeder, _headers, TestSessionLocal,
)
from app.models.evidence import Evidence


async def _evidence_raw(s, seeder, cam, v, **overrides):
    """Insert an Evidence row with explicit control over every mapped field."""
    defaults = dict(
        evidence_id=uuid.uuid4(), tenant_id=cam.tenant_id, campaign_id=cam.campaign_id,
        vendor_id=v.vendor_id, evidence_type="photo", latitude=19.5, longitude=73.0,
        verification_status="verified", verification_confidence=0.5,
        verification_flags=[], file_url="https://res.cloudinary.com/demo/x.jpg",
        thumbnail_url="https://res.cloudinary.com/demo/x_t.jpg", file_hash="c" * 64,
        capture_timestamp=datetime(2026, 7, 1, tzinfo=timezone.utc),
        created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
    )
    defaults.update(overrides)
    e = Evidence(**defaults)
    s.add(e)
    await s.flush()
    seeder.evidence_ids.append(e.evidence_id)
    return e


@pytest.mark.asyncio
async def test_all_four_verification_statuses_mapped(api_client, seeder):
    async with TestSessionLocal() as s:
        c = await seeder.client(s, f"st_{uuid.uuid4().hex[:8]}@x.com", "Status Co")
        cam = await seeder.campaign(s, c)
        v = await seeder.vendor(s, c)
        rows = {}
        for i, status in enumerate(["verified", "pending", "flagged", "rejected"]):
            rows[status] = await _evidence_raw(
                s, seeder, cam, v, latitude=19.0 + i * 0.01, longitude=72.0 + i * 0.01,
                verification_status=status,
            )
        await s.commit()

    resp = await api_client.get("/api/photos/locations", headers=_headers(c))
    assert resp.status_code == 200, resp.text
    by_id = {f["properties"]["photo_id"]: f for f in resp.json()["features"]}

    for status, row in rows.items():
        feat = by_id[str(row.evidence_id)]
        assert feat["properties"]["status"] == status


@pytest.mark.asyncio
async def test_confidence_and_flags_mapped_including_null_defaults(api_client, seeder):
    async with TestSessionLocal() as s:
        c = await seeder.client(s, f"cf_{uuid.uuid4().hex[:8]}@x.com", "Confidence Co")
        cam = await seeder.campaign(s, c)
        v = await seeder.vendor(s, c)
        with_vals = await _evidence_raw(
            s, seeder, cam, v, latitude=19.1, longitude=72.1,
            verification_confidence=0.77, verification_flags=["LOCATION_FAR_FROM_EXPECTED"],
        )
        with_nulls = await _evidence_raw(
            s, seeder, cam, v, latitude=19.2, longitude=72.2,
            verification_confidence=None, verification_flags=None,
        )
        await s.commit()

    resp = await api_client.get("/api/photos/locations", headers=_headers(c))
    assert resp.status_code == 200, resp.text
    by_id = {f["properties"]["photo_id"]: f for f in resp.json()["features"]}

    feat1 = by_id[str(with_vals.evidence_id)]
    assert feat1["properties"]["confidence"] == 0.77
    assert feat1["properties"]["flags"] == ["LOCATION_FAR_FROM_EXPECTED"]

    feat2 = by_id[str(with_nulls.evidence_id)]
    assert feat2["properties"]["confidence"] == 0, "NULL confidence must map to 0, not null"
    assert feat2["properties"]["flags"] == [], "NULL flags must map to [], not null"


@pytest.mark.asyncio
async def test_photo_url_is_file_url_direct_not_storage_resolved(api_client, seeder):
    """evidence.file_url is a full delivery URL already; it must be passed through
    verbatim, NOT re-resolved via the storage service (which expects a storage key,
    not a URL, and is only used by the legacy photos.s3_key path)."""
    async with TestSessionLocal() as s:
        c = await seeder.client(s, f"url_{uuid.uuid4().hex[:8]}@x.com", "URL Co")
        cam = await seeder.campaign(s, c)
        v = await seeder.vendor(s, c)
        row = await _evidence_raw(
            s, seeder, cam, v, latitude=19.3, longitude=72.3,
            file_url="https://res.cloudinary.com/demo/exact-url.jpg",
            thumbnail_url="https://res.cloudinary.com/demo/exact-thumb.jpg",
        )
        await s.commit()

    resp = await api_client.get("/api/photos/locations", headers=_headers(c))
    assert resp.status_code == 200, resp.text
    feat = next(f for f in resp.json()["features"] if f["properties"]["photo_id"] == str(row.evidence_id))
    assert feat["properties"]["photo_url"] == "https://res.cloudinary.com/demo/exact-url.jpg"
    assert feat["properties"]["thumbnail_url"] == "https://res.cloudinary.com/demo/exact-thumb.jpg"


@pytest.mark.asyncio
async def test_nullable_thumbnail_url_passes_through_as_null(api_client, seeder):
    """Non-photo evidence (e.g. voice_note) has no thumbnail; thumbnail_url must
    come back as null/None, not an empty string or an error."""
    async with TestSessionLocal() as s:
        c = await seeder.client(s, f"th_{uuid.uuid4().hex[:8]}@x.com", "Thumb Co")
        cam = await seeder.campaign(s, c)
        v = await seeder.vendor(s, c)
        row = await _evidence_raw(
            s, seeder, cam, v, latitude=19.4, longitude=72.4,
            evidence_type="voice_note", thumbnail_url=None,
            file_url="https://res.cloudinary.com/demo/voice.m4a",
        )
        await s.commit()

    resp = await api_client.get("/api/photos/locations", headers=_headers(c))
    assert resp.status_code == 200, resp.text
    feat = next(f for f in resp.json()["features"] if f["properties"]["photo_id"] == str(row.evidence_id))
    assert feat["properties"]["thumbnail_url"] is None
    assert feat["properties"]["photo_url"] == "https://res.cloudinary.com/demo/voice.m4a"


@pytest.mark.asyncio
async def test_captured_at_falls_back_to_created_at_when_capture_timestamp_null(api_client, seeder):
    async with TestSessionLocal() as s:
        c = await seeder.client(s, f"ca_{uuid.uuid4().hex[:8]}@x.com", "CapturedAt Co")
        cam = await seeder.campaign(s, c)
        v = await seeder.vendor(s, c)
        fixed_created = datetime(2026, 8, 15, 10, 30, tzinfo=timezone.utc)
        row = await _evidence_raw(
            s, seeder, cam, v, latitude=19.5, longitude=72.5,
            capture_timestamp=None, created_at=fixed_created,
        )
        await s.commit()

    resp = await api_client.get("/api/photos/locations", headers=_headers(c))
    assert resp.status_code == 200, resp.text
    feat = next(f for f in resp.json()["features"] if f["properties"]["photo_id"] == str(row.evidence_id))
    assert feat["properties"]["captured_at"] == fixed_created.isoformat()


@pytest.mark.asyncio
async def test_geometry_coordinate_order_is_lon_lat(api_client, seeder):
    """GeoJSON requires [longitude, latitude] order; verify evidence features follow it."""
    async with TestSessionLocal() as s:
        c = await seeder.client(s, f"geo_{uuid.uuid4().hex[:8]}@x.com", "Geo Co")
        cam = await seeder.campaign(s, c)
        v = await seeder.vendor(s, c)
        row = await _evidence_raw(s, seeder, cam, v, latitude=12.34, longitude=56.78)
        await s.commit()

    resp = await api_client.get("/api/photos/locations", headers=_headers(c))
    assert resp.status_code == 200, resp.text
    feat = next(f for f in resp.json()["features"] if f["properties"]["photo_id"] == str(row.evidence_id))
    lon, lat = feat["geometry"]["coordinates"]
    assert lon == pytest.approx(56.78)
    assert lat == pytest.approx(12.34)
