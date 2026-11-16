"""
Upload-side campaign authorization (POST /api/evidence/upload and POST /api/photos/upload).

Contract (accepted by the owner):
  * no campaign reference                    -> explicit Quick Capture (evidence endpoint only)
  * malformed / mismatched id + code         -> 400
  * nonexistent OR foreign-tenant campaign   -> 404, identical non-disclosing body
  * vendor not assigned to the campaign      -> 403
  * campaign not ACTIVE (completed/cancelled)-> 409 {"code": "CAMPAIGN_INACTIVE"}
  * an invalid or unknown reference NEVER falls back to Quick Capture
  * authorization happens BEFORE file validation/reads, storage writes, DB writes and
    geofence verification, so a rejected request leaves no storage object, no row and no
    verification data in the response.
Both endpoints apply the same rules (the legacy endpoint requires a campaign_code).

World (DEFAULT tenant unless noted), vendor V (created by client A):
  active_assigned     V assigned, ACTIVE            -> allowed
  completed_assigned  V assigned, COMPLETED         -> 409
  cancelled_assigned  V assigned, CANCELLED         -> 409
  unassigned          same tenant, V NOT assigned   -> 403
  other_client        another client's campaign, V NOT assigned -> 403
  foreign             OTHER tenant, V NOT assigned  -> 404
  foreign_assigned    OTHER tenant, V assigned (inconsistent data) -> 404
Foreign and unassigned campaigns carry a far-away geofence so any leaked verification result
would be visible.
"""
import io
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from PIL import Image
from sqlalchemy import delete, select, func

from tests.hotfix_support import hotfix_runtime_env  # noqa: F401
from tests.test_quick_capture_visibility import (  # noqa: F401
    _Sessions, OTHER_TENANT_ID, DEFAULT_TENANT_ID, _ensure_other_tenant, seed,
)
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.campaign import Campaign, CampaignType, CampaignStatus
from app.models.campaign_vendor_assignment import CampaignVendorAssignment
from app.models.evidence import Evidence
from app.models.location_profile import LocationProfile
from app.models.photo import Photo


# --------------------------------------------------------------------------- infrastructure
class _Recorder:
    """Counts storage writes (object storage must never be touched by a rejected request)."""
    photo_calls = 0
    cloudinary_calls = 0

    @classmethod
    def reset(cls):
        cls.photo_calls = 0
        cls.cloudinary_calls = 0

    def upload_photo_with_thumbnail(self, photo_bytes, campaign_id, photo_id):
        _Recorder.photo_calls += 1
        k = f"photos/{campaign_id}/{photo_id}.jpg"
        return k, f"http://mock/{k}", k + ".t", f"http://mock/{k}.t"


def _fake_cloudinary_upload(*a, **kw):
    _Recorder.cloudinary_calls += 1
    return {"public_id": "mock/pid", "secure_url": "https://mock.invalid/v.mp4"}


@pytest_asyncio.fixture
async def api(monkeypatch):
    import sys
    import types
    import app.api.evidence as ev_mod
    import app.api.photos as ph_mod
    _Recorder.reset()
    monkeypatch.setattr(ev_mod, "get_storage_service", lambda: _Recorder())
    monkeypatch.setattr(ph_mod, "get_storage_service", lambda: _Recorder())

    class _NoQuota:   # the legacy endpoint checks the campaign owner's subscription quota after the campaign gate
        async def check_photo_quota(self, *a, **k): return None
        async def check_storage_quota(self, *a, **k): return None
        async def increment_photo_usage(self, *a, **k): return None
        async def increment_storage_usage(self, *a, **k): return None
    monkeypatch.setattr(ph_mod, "get_quota_enforcer", lambda db: _NoQuota())
    # The video/voice path does `import cloudinary.uploader` inside the handler. The package is not installed in
    # the test environment, so inject a recording fake (also records any real-storage attempt in production code).
    fake_pkg = types.ModuleType("cloudinary")
    fake_up = types.ModuleType("cloudinary.uploader")
    fake_up.upload = _fake_cloudinary_upload
    fake_pkg.uploader = fake_up
    monkeypatch.setitem(sys.modules, "cloudinary", fake_pkg)
    monkeypatch.setitem(sys.modules, "cloudinary.uploader", fake_up)

    async def _ov():
        async with _Sessions() as s:
            yield s
    app.dependency_overrides[get_db] = _ov
    # raise_app_exceptions=False: an unhandled server error is returned as the real HTTP 500
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False),
                           base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


def _vhdr(vendor):
    tok = create_access_token({"sub": vendor.vendor_id, "type": "vendor", "vendor_id": vendor.vendor_id})
    return {"Authorization": f"Bearer {tok}"}


def _campaign(client, tenant, status=CampaignStatus.ACTIVE):
    return Campaign(
        campaign_id=uuid.uuid4(), tenant_id=tenant, client_id=client.client_id,
        campaign_code=f"UH-{uuid.uuid4().hex[:8].upper()}", name="authz",
        campaign_type=CampaignType.OOH_ADVERTISING,
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        status=status, created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
    )


def _far_geofence(campaign_id):
    return LocationProfile(
        profile_id=uuid.uuid4(), campaign_id=campaign_id,
        expected_latitude=40.0, expected_longitude=-70.0, tolerance_meters=50.0,
        created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
    )


def _jpeg():
    b = io.BytesIO()
    Image.new("RGB", (320, 240), (120, 130, 140)).save(b, "JPEG")
    return b.getvalue()


JPEG = _jpeg()
SENSORS = json.dumps({"gps_latitude": 19.0, "gps_longitude": 72.0, "gps_accuracy": 5.0})
NOW = datetime.now(tz=timezone.utc)


@pytest_asyncio.fixture
async def world(seed):
    w = SimpleNamespace(cids=[])
    async with _Sessions() as s:
        a = await seed.client(s)
        other = await seed.client(s)
        foreign_owner = await seed.client(s, tenant=OTHER_TENANT_ID)
        w.V = await seed.vendor(s, a)
        w.V.public_key = None            # legacy endpoint: an AUTHORIZED request stops at 401 (public key) after the gate
        spec = [
            ("active_assigned", a, DEFAULT_TENANT_ID, CampaignStatus.ACTIVE, True, False),
            ("completed_assigned", a, DEFAULT_TENANT_ID, CampaignStatus.COMPLETED, True, False),
            ("cancelled_assigned", a, DEFAULT_TENANT_ID, CampaignStatus.CANCELLED, True, False),
            ("unassigned", a, DEFAULT_TENANT_ID, CampaignStatus.ACTIVE, False, True),
            ("other_client", other, DEFAULT_TENANT_ID, CampaignStatus.ACTIVE, False, True),
            ("foreign", foreign_owner, OTHER_TENANT_ID, CampaignStatus.ACTIVE, False, True),
            ("foreign_assigned", foreign_owner, OTHER_TENANT_ID, CampaignStatus.ACTIVE, True, True),
        ]
        for name, owner, tenant, status, assigned, geofence in spec:
            c = _campaign(owner, tenant, status)
            s.add(c)
            await s.flush()
            if geofence:
                s.add(_far_geofence(c.campaign_id))
            if assigned:
                s.add(CampaignVendorAssignment(assignment_id=uuid.uuid4(), campaign_id=c.campaign_id,
                                               vendor_id=w.V.vendor_id))
            setattr(w, name, SimpleNamespace(id=str(c.campaign_id), code=c.campaign_code, uuid=c.campaign_id))
            w.cids.append(c.campaign_id)
        await s.commit()
    yield w
    async with _Sessions() as s:
        await s.execute(delete(Evidence).where(Evidence.vendor_id == w.V.vendor_id))
        await s.execute(delete(Photo).where(Photo.vendor_id == w.V.vendor_id))
        await s.execute(delete(CampaignVendorAssignment).where(CampaignVendorAssignment.campaign_id.in_(w.cids)))
        await s.execute(delete(LocationProfile).where(LocationProfile.campaign_id.in_(w.cids)))
        await s.execute(delete(Campaign).where(Campaign.campaign_id.in_(w.cids)))
        await s.commit()


async def _count(model, **where):
    async with _Sessions() as s:
        q = select(func.count()).select_from(model)
        for k, v in where.items():
            q = q.where(getattr(model, k) == v)
        return (await s.execute(q)).scalar()


def _json(r):
    try:
        return r.json()
    except Exception:
        return {}


# ------------------------------------------------------------------ request builders
async def post_evidence(api, vendor, *, etype="photo", cid=None, code=None, with_file=True, sensor=SENSORS,
                        android_extras=False):
    data = {"evidence_type": etype}
    if cid is not None:
        data["campaign_id"] = cid
    if code is not None:
        data["campaign_code"] = code
    if sensor:
        data["sensor_data"] = sensor
    if android_extras:   # exactly the extra parts the vc15 app sends
        data.update({"signature": json.dumps({"signature": "YWJj", "algorithm": "ECDSA-P256"}),
                     "gps_track": json.dumps([{"lat": 19.0, "lon": 72.0, "accuracy": 5.0, "timestamp_ms": 1}]),
                     "capture_timestamp": "2026-06-01T10:00:00Z"})
    files = None
    if with_file:
        files = {"file": ("x.mp4", b"\x00\x00video", "video/mp4")} if etype == "video" else \
                {"file": ("x.jpg", JPEG, "image/jpeg")}
        if android_extras:
            files["voice_note"] = ("voice.m4a", b"\x00audio", "audio/mp4")   # ignored by the backend
    return await api.post("/api/evidence/upload", data=data, files=files, headers=_vhdr(vendor))


VALID_SENSOR = json.dumps({"gps": {"latitude": 19.0, "longitude": 72.0, "accuracy": 5.0, "altitude": 0,
                                   "provider": "gps", "satellite_count": 8},
                           "location_hash": "h", "confidence_score": 0.9, "schema_version": "2.0"})
VALID_SIG = json.dumps({"signature": "YWJj", "algorithm": "ECDSA-P256", "device_id": "d1",
                        "timestamp": "2026-06-01T10:00:00+00:00", "location_hash": "h"})


async def post_legacy(api, vendor, code, *, photo_bytes=JPEG):
    return await api.post(
        "/api/photos/upload",
        data={"sensor_data": VALID_SENSOR, "signature": VALID_SIG, "campaign_code": code,
              "capture_timestamp": "2026-06-01T10:00:00+00:00"},
        files={"photo": ("photo.jpg", photo_bytes, "image/jpeg")}, headers=_vhdr(vendor))


LEAK_KEYS = {"evidence_id", "verification_status", "verification_confidence", "verification_flags",
             "signature_outcome", "file_url", "thumbnail_url"}


async def _assert_no_side_effects(w, label):
    assert _Recorder.photo_calls == 0, f"{label}: object storage written (photo)"
    assert _Recorder.cloudinary_calls == 0, f"{label}: object storage written (cloudinary)"
    assert await _count(Evidence, vendor_id=w.V.vendor_id) == 0, f"{label}: evidence row created"
    assert await _count(Photo, vendor_id=w.V.vendor_id) == 0, f"{label}: photo row created"


# =========================================================================== EVIDENCE ENDPOINT
EVIDENCE_REJECTIONS = [
    # label, kwargs (campaign refs resolved against the world), expected status
    ("foreign id", lambda w: dict(cid=w.foreign.id), 404),
    ("foreign code", lambda w: dict(code=w.foreign.code), 404),
    ("foreign-tenant campaign with a bad assignment row, id", lambda w: dict(cid=w.foreign_assigned.id), 404),
    ("foreign-tenant campaign with a bad assignment row, code", lambda w: dict(code=w.foreign_assigned.code), 404),
    ("nonexistent id", lambda w: dict(cid=str(uuid.uuid4())), 404),
    ("unknown code", lambda w: dict(code="NO-SUCH-CODE-XYZ"), 404),
    ("valid id + unknown code", lambda w: dict(cid=w.active_assigned.id, code="NO-SUCH-CODE-XYZ"), 404),
    ("same-tenant unassigned id", lambda w: dict(cid=w.unassigned.id), 403),
    ("same-tenant unassigned code", lambda w: dict(code=w.unassigned.code), 403),
    ("another client's campaign, not assigned", lambda w: dict(code=w.other_client.code), 403),
    ("completed id", lambda w: dict(cid=w.completed_assigned.id), 409),
    ("completed code", lambda w: dict(code=w.completed_assigned.code), 409),
    ("cancelled id", lambda w: dict(cid=w.cancelled_assigned.id), 409),
    ("cancelled code", lambda w: dict(code=w.cancelled_assigned.code), 409),
    ("malformed id", lambda w: dict(cid="not-a-uuid"), 400),
    ("id and code of different campaigns", lambda w: dict(cid=w.active_assigned.id, code=w.completed_assigned.code), 400),
]


@pytest.mark.asyncio
async def test_evidence_rejections_status_and_no_side_effects(api, world):
    w = world
    wrong = []
    for label, build, want in EVIDENCE_REJECTIONS:
        r = await post_evidence(api, w.V, **build(w))
        if r.status_code != want:
            wrong.append(f"{label}: got {r.status_code}, want {want}")
        leaked = LEAK_KEYS & set(_json(r))
        if leaked:
            wrong.append(f"{label}: response leaks {sorted(leaked)}")
    assert not wrong, "\n".join(wrong)
    await _assert_no_side_effects(w, "evidence rejections")


@pytest.mark.asyncio
async def test_evidence_video_rejection_never_reaches_object_storage(api, world):
    w = world
    for kw in (dict(cid=w.foreign.id), dict(code=w.unassigned.code), dict(cid=w.completed_assigned.id),
               dict(code="NO-SUCH-CODE-XYZ"), dict(cid=str(uuid.uuid4()))):
        r = await post_evidence(api, w.V, etype="video", **kw)
        assert r.status_code in (404, 403, 409), (kw, r.status_code)
    await _assert_no_side_effects(w, "evidence video rejections")


@pytest.mark.asyncio
async def test_evidence_foreign_and_nonexistent_are_indistinguishable(api, world):
    w = world
    bodies = []
    for kw in (dict(cid=w.foreign.id), dict(code=w.foreign.code), dict(cid=str(uuid.uuid4())),
               dict(code="NO-SUCH-CODE-XYZ"), dict(cid=w.foreign_assigned.id), dict(code=w.foreign_assigned.code)):
        r = await post_evidence(api, w.V, **kw)
        assert r.status_code == 404, (kw, r.status_code, r.text)
        bodies.append(r.content)
    assert len(set(bodies)) == 1, f"404 bodies differ: {set(bodies)}"


@pytest.mark.asyncio
async def test_evidence_inactive_contract_body(api, world):
    r = await post_evidence(api, world.V, cid=world.completed_assigned.id)
    assert r.status_code == 409
    detail = _json(r).get("detail")
    assert isinstance(detail, dict) and detail.get("code") == "CAMPAIGN_INACTIVE", r.text


@pytest.mark.asyncio
async def test_evidence_authorization_precedes_validation_and_file_handling(api, world):
    """An unauthorized request is rejected before request validation and file handling run."""
    w = world
    # photo type without a file would normally be 400 "File is required"
    r = await post_evidence(api, w.V, cid=w.foreign.id, with_file=False)
    assert r.status_code == 404, (r.status_code, r.text)
    r = await post_evidence(api, w.V, code=w.unassigned.code, with_file=False)
    assert r.status_code == 403, (r.status_code, r.text)
    # an invalid evidence_type must not mask a campaign rejection either
    r = await post_evidence(api, w.V, etype="bogus", cid=w.completed_assigned.id)
    assert r.status_code == 409, (r.status_code, r.text)
    await _assert_no_side_effects(w, "validation ordering")


@pytest.mark.asyncio
async def test_evidence_unknown_reference_never_falls_back_to_quick_capture(api, world):
    w = world
    for kw in (dict(code="NO-SUCH-CODE-XYZ"), dict(cid=str(uuid.uuid4())), dict(cid="garbage")):
        r = await post_evidence(api, w.V, **kw)
        assert r.status_code in (400, 404), (kw, r.status_code)
    assert await _count(Evidence, vendor_id=w.V.vendor_id) == 0


@pytest.mark.asyncio
async def test_evidence_quick_capture_without_reference_still_works(api, world):
    w = world
    for kw in (dict(), dict(cid="", code=""), dict(etype="text_note", with_file=False)):
        extra = dict(kw)
        if kw.get("etype") == "text_note":
            r = await api.post("/api/evidence/upload", data={"evidence_type": "text_note", "text_content": "note"},
                               headers=_vhdr(w.V))
        else:
            r = await post_evidence(api, w.V, **extra)
        assert r.status_code == 201, (kw, r.status_code, r.text)
    async with _Sessions() as s:
        rows = (await s.execute(select(Evidence.campaign_id).where(Evidence.vendor_id == w.V.vendor_id))).scalars().all()
    assert len(rows) == 3 and all(c is None for c in rows), rows


@pytest.mark.asyncio
async def test_evidence_assigned_active_upload_is_unchanged(api, world):
    w = world
    for label, kw in [("id", dict(cid=w.active_assigned.id)), ("code", dict(code=w.active_assigned.code)),
                      ("id+code (what the Android app sends)", dict(cid=w.active_assigned.id, code=w.active_assigned.code))]:
        r = await post_evidence(api, w.V, **kw)
        assert r.status_code == 201, (label, r.status_code, r.text)
        body = r.json()
        assert {"evidence_id", "verification_status", "verification_confidence", "verification_flags",
                "file_url", "thumbnail_url", "message"} <= set(body), body
    async with _Sessions() as s:
        rows = (await s.execute(select(Evidence.campaign_id).where(Evidence.vendor_id == w.V.vendor_id))).scalars().all()
    assert len(rows) == 3 and all(c == w.active_assigned.uuid for c in rows), rows


@pytest.mark.asyncio
async def test_evidence_android_request_contract_photo_and_video(api, world):
    """vc12-vc15 send campaign_id AND campaign_code together plus signature, gps_track, capture_timestamp
    and a voice_note part; Quick Capture sends neither reference."""
    w = world
    r = await post_evidence(api, w.V, etype="photo", cid=w.active_assigned.id, code=w.active_assigned.code,
                            android_extras=True)
    assert r.status_code == 201, r.text
    r = await post_evidence(api, w.V, etype="video", cid=w.active_assigned.id, code=w.active_assigned.code,
                            android_extras=True)
    assert r.status_code == 201, r.text
    assert _Recorder.cloudinary_calls == 1
    r = await post_evidence(api, w.V, etype="photo", android_extras=True)       # Quick Capture
    assert r.status_code == 201, r.text


# =========================================================================== LEGACY ENDPOINT
LEGACY_REJECTIONS = [
    ("foreign code", lambda w: w.foreign.code, 404),
    ("foreign-tenant campaign with a bad assignment row", lambda w: w.foreign_assigned.code, 404),
    ("nonexistent code", lambda w: "UH-DOES-NOT-EXIST", 404),
    ("same-tenant unassigned", lambda w: w.unassigned.code, 403),
    ("another client's campaign, not assigned", lambda w: w.other_client.code, 403),
    ("completed", lambda w: w.completed_assigned.code, 409),
    ("cancelled", lambda w: w.cancelled_assigned.code, 409),
]


@pytest.mark.asyncio
async def test_legacy_rejections_status_and_no_side_effects(api, world):
    w = world
    wrong = []
    for label, code_of, want in LEGACY_REJECTIONS:
        r = await post_legacy(api, w.V, code_of(w))
        if r.status_code != want:
            wrong.append(f"{label}: got {r.status_code}, want {want} ({_json(r).get('detail')})")
        if {"photo_id", "verification_status", "signature_valid", "s3_url"} & set(_json(r)):
            wrong.append(f"{label}: response leaks upload/verification fields")
    assert not wrong, "\n".join(wrong)
    await _assert_no_side_effects(w, "legacy rejections")


@pytest.mark.asyncio
async def test_legacy_foreign_and_nonexistent_are_indistinguishable(api, world):
    w = world
    bodies = []
    for code in (w.foreign.code, w.foreign_assigned.code, "UH-DOES-NOT-EXIST"):
        r = await post_legacy(api, w.V, code)
        assert r.status_code == 404, (code, r.status_code, r.text)
        bodies.append(r.content)
    assert len(set(bodies)) == 1, f"404 bodies differ (existence oracle): {set(bodies)}"
    assert "Campaign not found" in _json(r)["detail"]


@pytest.mark.asyncio
async def test_legacy_inactive_contract_body(api, world):
    r = await post_legacy(api, world.V, world.completed_assigned.code)
    assert r.status_code == 409
    detail = _json(r).get("detail")
    assert isinstance(detail, dict) and detail.get("code") == "CAMPAIGN_INACTIVE", r.text


@pytest.mark.asyncio
async def test_legacy_authorization_precedes_file_validation(api, world):
    """An unauthorized request is rejected before the uploaded file is read or validated."""
    w = world
    r = await post_legacy(api, w.V, w.foreign.code, photo_bytes=b"this is not a jpeg")
    assert r.status_code == 404, (r.status_code, r.text)
    r = await post_legacy(api, w.V, w.unassigned.code, photo_bytes=b"this is not a jpeg")
    assert r.status_code == 403, (r.status_code, r.text)
    await _assert_no_side_effects(w, "legacy ordering")


@pytest.mark.asyncio
async def test_legacy_blank_code_is_rejected_not_quick_capture(api, world):
    r = await post_legacy(api, world.V, "")
    assert r.status_code in (400, 404, 422), r.status_code
    await _assert_no_side_effects(world, "legacy blank code")


@pytest.mark.asyncio
async def test_legacy_assigned_active_passes_the_campaign_gate(api, world):
    """The vendor has no public key, so an authorized request proceeds past the campaign gate and stops at the
    existing 401 'public key not registered' check (before any storage or DB write). Existing end-to-end legacy
    success tests live in test_photo_upload.py."""
    r = await post_legacy(api, world.V, world.active_assigned.code)
    assert r.status_code == 401, (r.status_code, r.text)
    assert "public key" in _json(r).get("detail", "").lower()
    await _assert_no_side_effects(world, "legacy gate")


# =========================================================================== PARITY
@pytest.mark.asyncio
async def test_both_endpoints_apply_the_same_rules(api, world):
    w = world
    pairs = [("foreign", w.foreign), ("foreign_assigned", w.foreign_assigned), ("unassigned", w.unassigned),
             ("other_client", w.other_client), ("completed", w.completed_assigned), ("cancelled", w.cancelled_assigned)]
    diffs = []
    for name, c in pairs:
        ev = await post_evidence(api, w.V, code=c.code)
        lg = await post_legacy(api, w.V, c.code)
        if ev.status_code != lg.status_code:
            diffs.append(f"{name}: evidence={ev.status_code} legacy={lg.status_code}")
    assert not diffs, "\n".join(diffs)
