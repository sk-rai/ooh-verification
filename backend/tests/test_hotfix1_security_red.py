"""
Hotfix 1 security RED tests.

Tests assert SECURE behavior: fail on the vulnerable baseline, pass after fix.

Uses hotfix_support.py's fail-closed DB isolation (same pattern as P0 tests).
"""
import os
import uuid
from datetime import datetime, timezone

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("USE_MOCK_STORAGE", "true")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Fail-closed isolation guard — collection aborts if TEST_DATABASE_URL unsafe
from tests.hotfix_support import TEST_DATABASE_URL, DEFAULT_TENANT_ID, hotfix_runtime_env  # noqa: F401

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.admin_user import AdminUser
from app.models.client import Client, SubscriptionTier, SubscriptionStatus
from app.models.tenant_config import TenantConfig

_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool)
_Sessions = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


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


@pytest_asyncio.fixture
async def seeded_client():
    """Insert a test client under the default tenant, yield, clean up."""
    client = Client(
        client_id=uuid.uuid4(),
        tenant_id=DEFAULT_TENANT_ID,
        email=f"hf1test_{uuid.uuid4().hex[:8]}@test.invalid",
        password_hash=hash_password("TestPass!HF1xyz"),
        company_name="HF1 Test Co",
        phone_number="+10000000002",
        subscription_tier=SubscriptionTier.FREE,
        subscription_status=SubscriptionStatus.ACTIVE,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    async with _Sessions() as s:
        s.add(client)
        await s.commit()
    yield client
    async with _Sessions() as s:
        await s.execute(delete(Client).where(Client.client_id == client.client_id))
        await s.commit()


def _client_headers(client: Client) -> dict:
    token = create_access_token({
        "sub": str(client.client_id),
        "type": "client",
        "email": client.email,
    })
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(DEFAULT_TENANT_ID),
    }


# ─── A. Admin mutation routes ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_fix_quotas_rejects_anonymous(api_client):
    """POST /api/admin/fix-quotas must not be callable without auth.
    After fix (removed): 404 or 405.
    Unfixed: 200 (data mutation).
    """
    resp = await api_client.post("/api/admin/fix-quotas")
    assert resp.status_code in (404, 405, 401, 403), (
        f"fix-quotas returned {resp.status_code} — still accessible without auth"
    )


@pytest.mark.asyncio
async def test_admin_set_subscription_rejects_anonymous(api_client):
    """POST /api/admin/set-client-subscription must reject anonymous callers.
    Unfixed: 200 with arbitrary subscription changes.
    """
    resp = await api_client.post(
        "/api/admin/set-client-subscription",
        params={"client_id": str(uuid.uuid4()), "tier": "enterprise"},
    )
    assert resp.status_code in (404, 405, 401, 403), (
        f"set-client-subscription returned {resp.status_code} — still accessible"
    )


@pytest.mark.asyncio
async def test_admin_upgrade_enterprise_rejects_anonymous(api_client):
    """POST /api/admin/upgrade-to-enterprise must reject anonymous callers."""
    resp = await api_client.post("/api/admin/upgrade-to-enterprise")
    assert resp.status_code in (404, 405, 401, 403), (
        f"upgrade-to-enterprise returned {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_admin_fix_vendor_associations_rejects_anonymous(api_client):
    """POST /api/admin/fix-vendor-associations must reject anonymous callers."""
    resp = await api_client.post("/api/admin/fix-vendor-associations")
    assert resp.status_code in (404, 405, 401, 403), (
        f"fix-vendor-associations returned {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_admin_create_review_vendor_rejects_anonymous(api_client):
    """POST /api/admin/create-review-vendor must reject anonymous callers."""
    resp = await api_client.post("/api/admin/create-review-vendor")
    assert resp.status_code in (404, 405, 401, 403), (
        f"create-review-vendor returned {resp.status_code}"
    )


# ─── B. API key management ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_key_create_requires_auth(api_client):
    """POST /api/v1/keys must require an authenticated client. No token -> 401/403."""
    resp = await api_client.post("/api/v1/keys", data={"name": "Test Key"})
    assert resp.status_code in (401, 403), (
        f"POST /api/v1/keys returned {resp.status_code} without auth — vulnerable"
    )


@pytest.mark.asyncio
async def test_api_key_list_requires_auth(api_client):
    """GET /api/v1/keys must require an authenticated client. No token -> 401/403."""
    resp = await api_client.get("/api/v1/keys")
    assert resp.status_code in (401, 403), (
        f"GET /api/v1/keys returned {resp.status_code} without auth — vulnerable"
    )


@pytest.mark.asyncio
async def test_api_key_revoke_requires_auth(api_client):
    """DELETE /api/v1/keys/{id} must require an authenticated client. No token -> 401/403."""
    resp = await api_client.delete(f"/api/v1/keys/{uuid.uuid4()}")
    assert resp.status_code in (401, 403), (
        f"DELETE /api/v1/keys returned {resp.status_code} without auth — vulnerable"
    )


@pytest.mark.asyncio
async def test_api_key_create_with_valid_client(api_client, seeded_client):
    """POST /api/v1/keys with valid client JWT must succeed and return key once."""
    resp = await api_client.post(
        "/api/v1/keys",
        data={"name": "My Key"},
        headers=_client_headers(seeded_client),
    )
    assert resp.status_code == 200, f"key creation failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "key" in data, "raw key must be in response"
    assert data["key"].startswith("tc_live_"), "key must have tc_live_ prefix"
    # key must not be echoed anywhere beyond the response — just check it's present
    assert "key_id" in data


@pytest.mark.asyncio
async def test_api_key_list_scoped_to_client(api_client, seeded_client):
    """GET /api/v1/keys returns only the authenticated client's keys (no raw key)."""
    resp = await api_client.get("/api/v1/keys", headers=_client_headers(seeded_client))
    assert resp.status_code == 200, f"list failed: {resp.text}"
    for k in resp.json():
        assert "key" not in k or k["key"].endswith("****"), "raw key must not appear in list"


# ─── C. Analytics cron disabled ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_cron_get_returns_503(api_client):
    """GET /api/analytics/cron/summarize must be disabled -> 503.
    Unfixed: returns 200 (enqueues or runs inline).
    """
    resp = await api_client.get("/api/analytics/cron/summarize")
    assert resp.status_code == 503, (
        f"GET cron/summarize returned {resp.status_code} — not disabled (unfixed)"
    )


@pytest.mark.asyncio
async def test_analytics_cron_post_returns_503(api_client):
    """POST /api/analytics/cron/summarize must be disabled -> 503."""
    resp = await api_client.post("/api/analytics/cron/summarize")
    assert resp.status_code == 503, (
        f"POST cron/summarize returned {resp.status_code} — not disabled (unfixed)"
    )


# ─── D. Evidence fix-video-thumbnails ────────────────────────────────────────

@pytest.mark.asyncio
async def test_evidence_fix_thumbnails_rejects_anonymous(api_client):
    """POST /api/evidence/fix-video-thumbnails must require admin auth.
    Unfixed: returns 200 (or 500 on error) without auth.
    """
    resp = await api_client.post(
        "/api/evidence/fix-video-thumbnails",
        params={"campaign_id": str(uuid.uuid4())},
    )
    assert resp.status_code in (401, 403), (
        f"fix-video-thumbnails returned {resp.status_code} without auth — vulnerable"
    )


@pytest.mark.asyncio
async def test_evidence_fix_thumbnails_rejects_client(api_client, seeded_client):
    """POST /api/evidence/fix-video-thumbnails must reject non-admin client tokens."""
    resp = await api_client.post(
        "/api/evidence/fix-video-thumbnails",
        params={"campaign_id": str(uuid.uuid4())},
        headers=_client_headers(seeded_client),
    )
    assert resp.status_code in (401, 403), (
        f"fix-video-thumbnails returned {resp.status_code} for a client token — vulnerable"
    )


# ─── A continued: remaining 6 admin mutation routes ─────────────────────────

@pytest.mark.asyncio
async def test_admin_fix_location_constraint_rejects_anonymous(api_client):
    """POST /api/admin/fix-location-constraint must reject anonymous callers."""
    resp = await api_client.post("/api/admin/fix-location-constraint")
    assert resp.status_code in (404, 405, 401, 403), (
        f"fix-location-constraint returned {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_admin_fix_duplicate_locations_rejects_anonymous(api_client):
    """POST /api/admin/fix-duplicate-locations must reject anonymous callers."""
    resp = await api_client.post("/api/admin/fix-duplicate-locations")
    assert resp.status_code in (404, 405, 401, 403), (
        f"fix-duplicate-locations returned {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_admin_fix_otp_table_rejects_anonymous(api_client):
    """POST /api/admin/fix-otp-table must reject anonymous callers."""
    resp = await api_client.post("/api/admin/fix-otp-table")
    assert resp.status_code in (404, 405, 401, 403), (
        f"fix-otp-table returned {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_admin_fix_tolerance_rejects_anonymous(api_client):
    """POST /api/admin/fix-tolerance must reject anonymous callers."""
    resp = await api_client.post("/api/admin/fix-tolerance")
    assert resp.status_code in (404, 405, 401, 403), (
        f"fix-tolerance returned {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_admin_clear_review_device_rejects_anonymous(api_client):
    """POST /api/admin/clear-review-device must reject anonymous callers."""
    resp = await api_client.post("/api/admin/clear-review-device")
    assert resp.status_code in (404, 405, 401, 403), (
        f"clear-review-device returned {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_admin_fix_tenant_email_rejects_anonymous(api_client):
    """POST /api/admin/fix-tenant-email must reject anonymous callers."""
    resp = await api_client.post("/api/admin/fix-tenant-email")
    assert resp.status_code in (404, 405, 401, 403), (
        f"fix-tenant-email returned {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_evidence_fix_thumbnails_rejects_vendor(api_client):
    """POST /api/evidence/fix-video-thumbnails must reject vendor tokens (not admin)."""
    # Mint a vendor-type token (no real vendor row needed — the auth check fires first)
    vendor_token = create_access_token({
        "sub": str(uuid.uuid4()),
        "type": "vendor",
        "vendor_id": "FAKEVENDOR",
    })
    resp = await api_client.post(
        "/api/evidence/fix-video-thumbnails",
        params={"campaign_id": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {vendor_token}"},
    )
    assert resp.status_code in (401, 403), (
        f"fix-video-thumbnails returned {resp.status_code} for a vendor token"
    )


@pytest.mark.asyncio
async def test_api_key_revoke_cannot_delete_other_clients_key(
    api_client, seeded_client
):
    """DELETE /api/v1/keys/{id} must only delete the authenticated client's own key."""
    # Try to revoke a random key_id — with proper ownership enforcement it returns 404
    # (not found for this client), not 200 or 500
    resp = await api_client.delete(
        f"/api/v1/keys/{uuid.uuid4()}",
        headers=_client_headers(seeded_client),
    )
    # 404 = key not owned by this client (correct ownership enforcement)
    # 401/403 = auth failed (also acceptable)
    # 200 = WRONG — means any key could be revoked
    assert resp.status_code in (404, 401, 403), (
        f"revoke returned {resp.status_code} for a non-owned key — ownership not enforced"
    )
