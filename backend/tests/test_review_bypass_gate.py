"""
Security tests for the REVIEW authentication bypass gate.

Requirements verified:
  1. Bypass disabled by default (PLAY_STORE_REVIEW_ENABLED absent or false).
  2. Bypass disabled when explicitly set to false.
  3. Previously issued REVIEW JWT (vendor_id=REVIEW) is rejected by all protected vendor endpoints.
  4. Normal vendor OTP authentication and authorization unchanged.
  5. No unintended cross-tenant access through the REVIEW path.

The REVIEW vendor does not exist in the test database; we rely on the dependency
rejecting the vendor_id before the DB lookup reaches any real row.
"""
import json
import os
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.vendor import Vendor, VendorStatus
from tests.test_quick_capture_visibility import _Sessions, DEFAULT_TENANT_ID, _ensure_other_tenant  # noqa: F401
from tests.hotfix_support import hotfix_runtime_env  # noqa: F401


# --------------------------------------------------------------------------- fixtures
@pytest.fixture
async def api_client():
    async def _ov():
        async with _Sessions() as s:
            yield s
    app.dependency_overrides[get_db] = _ov
    # Ensure otp_codes table exists (the bypass code uses AsyncSessionLocal, not the override)
    from sqlalchemy import text
    from app.core.database import AsyncSessionLocal as _ASL
    async with _ASL() as s:
        await s.execute(text("""
            CREATE TABLE IF NOT EXISTS otp_codes (
                phone_number VARCHAR PRIMARY KEY,
                otp VARCHAR NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0
            )
        """))
        await s.commit()
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False),
                           base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
    # Clean up any REVIEW OTP rows
    async with _ASL() as s:
        await s.execute(text("DELETE FROM otp_codes WHERE phone_number = '+911234567890'"))
        await s.commit()


def _review_jwt():
    """The exact JWT the old bypass issued — vendor_id=REVIEW, type=vendor, no tenant."""
    return create_access_token({"sub": "REVIEW", "type": "vendor", "vendor_id": "REVIEW"})


def _real_vendor_jwt(vendor_id):
    return create_access_token({"sub": vendor_id, "type": "vendor", "vendor_id": vendor_id})


async def _make_real_vendor(session, tenant_id=None):
    """Create a vendor with a real client FK to satisfy created_by_client_id."""
    import uuid as _uuid
    from app.models.client import Client, SubscriptionStatus
    tid = uuid.UUID(str(tenant_id or DEFAULT_TENANT_ID))
    cid = uuid.uuid4()
    c = Client(
        client_id=cid, tenant_id=tid, email=f"rv-test-{_uuid.uuid4().hex[:6]}@example.test",
        password_hash="x", company_name="RV Test Co", phone_number="+10000000098",
        subscription_tier="free", subscription_status=SubscriptionStatus.ACTIVE,
        created_at=datetime.now(tz=timezone.utc), updated_at=datetime.now(tz=timezone.utc),
    )
    session.add(c)
    await session.flush()
    v = Vendor(
        vendor_id="V00RV1",
        tenant_id=tid,
        created_by_client_id=cid,
        name="RV Test Vendor",
        phone_number="+10000000099",
        status=VendorStatus.ACTIVE,
        device_verified=True,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    session.add(v)
    await session.flush()
    return v


# --------------------------------------------------------------------------- OTP bypass gate
@pytest.mark.asyncio
async def test_review_otp_bypass_disabled_by_default(api_client, monkeypatch):
    """With no env var set, the REVIEW bypass does not fire."""
    monkeypatch.delenv("PLAY_STORE_REVIEW_ENABLED", raising=False)
    r = await api_client.post("/api/auth/vendor/request-otp",
                              json={"vendor_id": "REVIEW", "phone_number": "+911234567890"})
    # Normal OTP path: vendor lookup with tenant from middleware. The REVIEW vendor
    # does not exist in the test database, so we get 404 "Vendor not found".
    # We do NOT get the bypass 200 "OTP sent successfully" with expires_in=86400.
    assert r.status_code == 404
    assert "86400" not in r.text


@pytest.mark.asyncio
async def test_review_otp_bypass_disabled_when_false(api_client, monkeypatch):
    monkeypatch.setenv("PLAY_STORE_REVIEW_ENABLED", "false")
    r = await api_client.post("/api/auth/vendor/request-otp",
                              json={"vendor_id": "REVIEW", "phone_number": "+911234567890"})
    assert r.status_code == 404
    assert "86400" not in r.text


@pytest.mark.asyncio
async def test_review_otp_bypass_fires_when_enabled(api_client, monkeypatch):
    """When explicitly enabled (staging only), the bypass works as intended."""
    monkeypatch.setenv("PLAY_STORE_REVIEW_ENABLED", "true")
    r = await api_client.post("/api/auth/vendor/request-otp",
                              json={"vendor_id": "REVIEW", "phone_number": "+911234567890"})
    # Bypass fires: 200 with expires_in=86400
    assert r.status_code == 200
    assert r.json().get("expires_in") == 86400


@pytest.mark.asyncio
async def test_review_verify_otp_bypass_disabled_by_default(api_client, monkeypatch):
    monkeypatch.delenv("PLAY_STORE_REVIEW_ENABLED", raising=False)
    r = await api_client.post("/api/auth/vendor/verify-otp",
                              json={"vendor_id": "REVIEW", "phone_number": "+911234567890", "otp": "123456"})
    # OTP not in the test database (no bypass wrote it), so: 401 Invalid or expired OTP.
    # We definitely do NOT get a JWT back.
    assert r.status_code in (401, 404)
    assert "access_token" not in r.text


# --------------------------------------------------------------------------- previously issued REVIEW JWT rejected
@pytest.mark.asyncio
async def test_review_jwt_rejected_by_evidence_upload(api_client, monkeypatch):
    monkeypatch.delenv("PLAY_STORE_REVIEW_ENABLED", raising=False)
    tok = _review_jwt()
    r = await api_client.post("/api/evidence/upload",
                              data={"evidence_type": "photo"},
                              headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
    assert "not permitted" in r.text.lower()


@pytest.mark.asyncio
async def test_review_jwt_rejected_by_photos_upload(api_client, monkeypatch):
    monkeypatch.delenv("PLAY_STORE_REVIEW_ENABLED", raising=False)
    tok = _review_jwt()
    r = await api_client.post("/api/photos/upload",
                              data={"sensor_data": "{}", "signature": "{}", "campaign_code": "X",
                                    "capture_timestamp": "2026-01-01T00:00:00Z"},
                              files={"photo": ("x.jpg", b"junk", "image/jpeg")},
                              headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
    assert "not permitted" in r.text.lower()


@pytest.mark.asyncio
async def test_review_jwt_rejected_by_tracks_sync(api_client, monkeypatch):
    monkeypatch.delenv("PLAY_STORE_REVIEW_ENABLED", raising=False)
    tok = _review_jwt()
    r = await api_client.post("/api/tracks/sync",
                              json={"track_date": "2026-01-01", "points": [], "point_count": 0},
                              headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_review_jwt_rejected_by_vendor_campaigns(api_client, monkeypatch):
    monkeypatch.delenv("PLAY_STORE_REVIEW_ENABLED", raising=False)
    tok = _review_jwt()
    r = await api_client.get("/api/vendors/me/campaigns",
                             headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


# --------------------------------------------------------------------------- normal vendor auth unchanged
@pytest.mark.asyncio
async def test_normal_vendor_otp_flow_unaffected(api_client, monkeypatch):
    """The REVIEW gate does not affect real vendor logins."""
    monkeypatch.delenv("PLAY_STORE_REVIEW_ENABLED", raising=False)
    async with _Sessions() as s:
        v = await _make_real_vendor(s)
        await s.commit()
    try:
        tok = _real_vendor_jwt(v.vendor_id)
        # A real vendor token with a real vendor row should work.
        r = await api_client.post("/api/evidence/upload",
                                  data={"evidence_type": "photo"},
                                  headers={"Authorization": f"Bearer {tok}"})
        # Authorization passes the dep; the upload hits request validation (no file) → 400
        assert r.status_code == 400 and "File is required" in r.text, \
            f"expected 400 from request validation, got {r.status_code}: {r.text[:200]}"
    finally:
        async with _Sessions() as s:
            await s.execute(delete(Vendor).where(Vendor.vendor_id == v.vendor_id))
            await s.commit()


@pytest.mark.asyncio
async def test_review_jwt_accepted_when_staging_flag_on(api_client, monkeypatch):
    """When PLAY_STORE_REVIEW_ENABLED=true, a REVIEW JWT still falls through to vendor lookup.
    The REVIEW vendor does not exist in the test database, so it returns 404 (not 403).
    This confirms the safeguard in get_current_vendor is off when the flag is on."""
    monkeypatch.setenv("PLAY_STORE_REVIEW_ENABLED", "true")
    tok = _review_jwt()
    r = await api_client.post("/api/evidence/upload",
                              data={"evidence_type": "photo"},
                              headers={"Authorization": f"Bearer {tok}"})
    # In staging the guard is off, so we fall through to the DB lookup: REVIEW not in test DB → 404
    assert r.status_code == 404, f"expected 404 (vendor not in test DB), got {r.status_code}: {r.text[:200]}"


# --------------------------------------------------------------------------- cross-tenant safety
@pytest.mark.asyncio
async def test_review_jwt_cannot_access_campaigns_even_via_client_endpoint(api_client, monkeypatch):
    """Client endpoints reject the REVIEW token because it has type=vendor, not type=client."""
    monkeypatch.delenv("PLAY_STORE_REVIEW_ENABLED", raising=False)
    tok = _review_jwt()
    r = await api_client.get("/api/reports/campaigns",
                             headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code in (401, 403)
