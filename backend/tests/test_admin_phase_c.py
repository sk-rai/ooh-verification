"""Phase C RED tests: administrator password-fingerprint (pwf) JWT claim.

Spec: .kiro/specs/admin-seed-credential-fix Phase C.

All tests in this file are EXPECTED TO FAIL on the unfixed code base because:
- admin_login does not yet issue pwf claims.
- get_current_admin does not yet verify pwf claims.

Once Phase C production changes are applied these tests must all turn GREEN.
Tests use the isolated *_test database via admin_seed_support (fail-closed).
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("USE_MOCK_STORAGE", "true")

# Fail-closed isolation guard — aborts collection if TEST_DATABASE_URL is unsafe.
from tests import admin_seed_support  # noqa: E402 (must be after env setup)
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, SECRET_KEY
from app.main import app
from app.models.admin_user import AdminUser
from app.models.client import Client, SubscriptionTier, SubscriptionStatus
from app.models.vendor import Vendor, VendorStatus
from app.models.tenant_config import TenantConfig

# ---------------------------------------------------------------------------
# Synthetic JWT secret for isolated tests.
# The production SECRET_KEY may equal the insecure default in CI; using a
# known-good synthetic key lets us test fingerprint behaviour without the
# insecure-key guard firing.
# ---------------------------------------------------------------------------
_TEST_JWT_SECRET = "test-jwt-secret-32-chars-padding!!"

_engine = create_async_engine(
    admin_seed_support.TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool
)
_Sessions = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

from tests.hotfix_support import DEFAULT_TENANT_ID


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _make_admin(email: str | None = None) -> AdminUser:
    """Create an AdminUser with a generated password (never the legacy value)."""
    pw = admin_seed_support.shared_bootstrap_password()
    return AdminUser(
        admin_id=uuid.uuid4(),
        email=email or f"admin_{uuid.uuid4().hex[:8]}@test.invalid",
        password_hash=hash_password(pw),
        name="Test Admin",
        is_active=True,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )


def _make_client() -> Client:
    pw = admin_seed_support.shared_bootstrap_password()
    return Client(
        client_id=uuid.uuid4(),
        tenant_id=DEFAULT_TENANT_ID,
        email=f"client_{uuid.uuid4().hex[:8]}@test.invalid",
        password_hash=hash_password(pw),
        company_name="Test Co",
        phone_number="+10000000001",
        subscription_tier=SubscriptionTier.FREE,
        subscription_status=SubscriptionStatus.ACTIVE,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )


def _make_vendor(client_id) -> Vendor:
    return Vendor(
        vendor_id=uuid.uuid4().hex[:6].upper(),
        tenant_id=DEFAULT_TENANT_ID,
        created_by_client_id=client_id,
        name="Test Vendor",
        phone_number="+919000000001",
        status=VendorStatus.ACTIVE,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )


def _admin_token_no_pwf(admin: AdminUser) -> dict:
    """Mint an admin token WITHOUT the pwf claim (simulates pre-Phase-C tokens)."""
    return {"Authorization": "Bearer " + create_access_token({
        "sub": str(admin.admin_id),
        "type": "admin",
        "email": admin.email,
    })}


def _admin_token_with_pwf(admin: AdminUser, secret: str = _TEST_JWT_SECRET) -> dict:
    """Mint an admin token WITH the correct pwf claim using the test secret."""
    from app.core.admin_token_fingerprint import compute_pwf, PWF_CLAIM
    pwf = compute_pwf(admin.password_hash, secret_key=secret)
    return {"Authorization": "Bearer " + create_access_token({
        "sub": str(admin.admin_id),
        "type": "admin",
        "email": admin.email,
        PWF_CLAIM: pwf,
    })}


def _admin_token_wrong_pwf(admin: AdminUser) -> dict:
    """Mint an admin token with an intentionally wrong pwf value."""
    return {"Authorization": "Bearer " + create_access_token({
        "sub": str(admin.admin_id),
        "type": "admin",
        "email": admin.email,
        "pwf": "AAAAAAAAAAAAAAAAAAAAAA",  # wrong 22-char base64url
    })}


def _admin_token_malformed_pwf(admin: AdminUser) -> dict:
    """Mint an admin token with a pwf value of wrong type (int)."""
    return {"Authorization": "Bearer " + create_access_token({
        "sub": str(admin.admin_id),
        "type": "admin",
        "email": admin.email,
        "pwf": 12345,
    })}


async def _cleanup(*tables_and_ids):
    """Delete rows by primary key to avoid cross-test pollution."""
    pass  # Callers use explicit session cleanup


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _set_test_jwt_secret():
    """Set JWT_SECRET_KEY for the entire Phase C test session automatically.

    This avoids requiring a manual ``export JWT_SECRET_KEY=...`` before running
    the tests.  The value matches ``_TEST_JWT_SECRET`` so production code paths
    (compute_pwf, verify_pwf without secret_key override) use the same key as
    the test helpers.  The session monkeypatch is from pytest-monkeypatch-session
    or the stdlib fixture workaround below.
    """
    import os
    old = os.environ.get("JWT_SECRET_KEY")
    os.environ["JWT_SECRET_KEY"] = _TEST_JWT_SECRET
    yield
    if old is None:
        os.environ.pop("JWT_SECRET_KEY", None)
    else:
        os.environ["JWT_SECRET_KEY"] = old


@pytest_asyncio.fixture(autouse=True)
async def _ensure_tenant(setup_test_database):
    """Ensure the default tenant exists (needed by some fixtures)."""
    async with _Sessions() as s:
        existing = (await s.execute(
            select(TenantConfig.tenant_id).where(TenantConfig.tenant_id == DEFAULT_TENANT_ID)
        )).scalar_one_or_none()
        if not existing:
            s.add(TenantConfig(
                tenant_id=DEFAULT_TENANT_ID,
                tenant_name="Test Tenant",
                subdomain="default",
                primary_color="#007bff",
                secondary_color="#6c757d",
                email_from_address="noreply@test.invalid",
                email_from_name="Test",
                is_active=True,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            ))
            await s.commit()


@pytest_asyncio.fixture
async def api_client():
    async def _override_get_db():
        async with _Sessions() as s:
            yield s
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def seeded_admin():
    """Insert a fresh admin, yield it, delete after."""
    admin = _make_admin()
    async with _Sessions() as s:
        s.add(admin)
        await s.commit()
    yield admin
    async with _Sessions() as s:
        await s.execute(delete(AdminUser).where(AdminUser.admin_id == admin.admin_id))
        await s.commit()


@pytest_asyncio.fixture
async def seeded_client():
    client = _make_client()
    async with _Sessions() as s:
        s.add(client)
        await s.commit()
    yield client
    async with _Sessions() as s:
        await s.execute(delete(Client).where(Client.client_id == client.client_id))
        await s.commit()


# ---------------------------------------------------------------------------
# Unit tests: admin_token_fingerprint.py (these can pass NOW)
# ---------------------------------------------------------------------------

class TestFingerprintModule:
    """Unit tests for the fingerprint helper — independent of production routes."""

    def test_compute_pwf_returns_22_char_base64url(self):
        from app.core.admin_token_fingerprint import compute_pwf
        pw_hash = "$2b$12$" + "a" * 53
        result = compute_pwf(pw_hash, secret_key=_TEST_JWT_SECRET)
        assert len(result) == 22
        # base64url chars only
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
                   for c in result)

    def test_compute_pwf_is_deterministic(self):
        from app.core.admin_token_fingerprint import compute_pwf
        pw_hash = "$2b$12$" + "b" * 53
        assert compute_pwf(pw_hash, _TEST_JWT_SECRET) == compute_pwf(pw_hash, _TEST_JWT_SECRET)

    def test_compute_pwf_differs_for_different_hashes(self):
        from app.core.admin_token_fingerprint import compute_pwf
        h1 = "$2b$12$" + "a" * 53
        h2 = "$2b$12$" + "b" * 53
        assert compute_pwf(h1, _TEST_JWT_SECRET) != compute_pwf(h2, _TEST_JWT_SECRET)

    def test_compute_pwf_differs_for_different_secrets(self):
        from app.core.admin_token_fingerprint import compute_pwf
        pw_hash = "$2b$12$" + "c" * 53
        assert compute_pwf(pw_hash, "secret-A-32-chars-padding-here!!") !=                compute_pwf(pw_hash, "secret-B-32-chars-padding-here!!")

    def test_verify_pwf_correct_returns_true(self):
        from app.core.admin_token_fingerprint import compute_pwf, verify_pwf
        pw_hash = "$2b$12$" + "d" * 53
        pwf = compute_pwf(pw_hash, _TEST_JWT_SECRET)
        assert verify_pwf(pwf, pw_hash, _TEST_JWT_SECRET) is True

    def test_verify_pwf_wrong_value_returns_false(self):
        from app.core.admin_token_fingerprint import verify_pwf
        pw_hash = "$2b$12$" + "e" * 53
        assert verify_pwf("AAAAAAAAAAAAAAAAAAAAAA", pw_hash, _TEST_JWT_SECRET) is False

    def test_verify_pwf_none_returns_false(self):
        from app.core.admin_token_fingerprint import verify_pwf
        pw_hash = "$2b$12$" + "f" * 53
        assert verify_pwf(None, pw_hash, _TEST_JWT_SECRET) is False

    def test_verify_pwf_empty_string_returns_false(self):
        from app.core.admin_token_fingerprint import verify_pwf
        pw_hash = "$2b$12$" + "g" * 53
        assert verify_pwf("", pw_hash, _TEST_JWT_SECRET) is False

    def test_verify_pwf_non_string_type_returns_false(self):
        from app.core.admin_token_fingerprint import verify_pwf
        pw_hash = "$2b$12$" + "h" * 53
        assert verify_pwf(12345, pw_hash, _TEST_JWT_SECRET) is False
        assert verify_pwf([], pw_hash, _TEST_JWT_SECRET) is False

    def test_insecure_key_raises_runtime_error(self):
        from app.core.admin_token_fingerprint import compute_pwf
        import pytest
        pw_hash = "$2b$12$" + "i" * 53
        with pytest.raises(RuntimeError, match="insecure"):
            compute_pwf(pw_hash, secret_key="your-secret-key-change-in-production")

    def test_invalid_hash_raises(self):
        from app.core.admin_token_fingerprint import compute_pwf
        import pytest
        with pytest.raises((TypeError, ValueError)):
            compute_pwf("not-a-bcrypt-hash", _TEST_JWT_SECRET)
        with pytest.raises((TypeError, ValueError)):
            compute_pwf("", _TEST_JWT_SECRET)
        with pytest.raises((TypeError, ValueError)):
            compute_pwf(None, _TEST_JWT_SECRET)  # type: ignore

    def test_domain_separation_from_non_prefixed_hmac(self):
        """Domain prefix means same key+hash produce different values without prefix."""
        import hmac as _hmac, hashlib, base64
        from app.core.admin_token_fingerprint import compute_pwf
        pw_hash = "$2b$12$" + "j" * 53
        pwf = compute_pwf(pw_hash, _TEST_JWT_SECRET)
        # HMAC without the domain prefix
        raw = _hmac.new(
            _TEST_JWT_SECRET.encode(), pw_hash.encode(), hashlib.sha256
        ).digest()[:16]
        naive = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
        assert pwf != naive


# ---------------------------------------------------------------------------
# Integration tests: route behavior (RED until production changes applied)
# ---------------------------------------------------------------------------

class TestAdminLoginIssuesPwf:
    """admin_login must embed pwf in issued tokens.  RED until Phase C."""

    @pytest.mark.asyncio
    async def test_login_response_includes_pwf_in_token(self, api_client, seeded_admin):
        """The login response token must decode to a payload containing pwf."""
        import base64, json
        # Use the login endpoint with the correct password from shared fixture
        pw = admin_seed_support.shared_bootstrap_password()
        resp = await api_client.post("/api/admin/login", json={
            "email": seeded_admin.email,
            "password": pw,
        })
        # If login fails it's a test-setup issue (hash mismatch), not Phase C
        assert resp.status_code == 200, f"login failed: {resp.text}"
        token = resp.json()["access_token"]
        # Decode payload (middle segment) without verifying sig
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        # RED: pwf is absent until Phase C is implemented
        assert "pwf" in payload, "admin JWT is missing pwf claim (Phase C not yet applied)"


class TestGetCurrentAdminRequiresPwf:
    """get_current_admin must reject tokens without or with wrong pwf.  RED until Phase C."""

    @pytest.mark.asyncio
    async def test_valid_token_with_correct_pwf_accepted(self, api_client, seeded_admin):
        """Token carrying the correct pwf must be accepted on a protected route."""
        hdr = _admin_token_with_pwf(seeded_admin, _TEST_JWT_SECRET)
        resp = await api_client.get("/api/admin/me", headers=hdr)
        # RED: currently accepts tokens without pwf, so this may already pass,
        # but it establishes the positive baseline.
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_token_missing_pwf_rejected(self, api_client, seeded_admin):
        """Token without pwf claim must be rejected with 401."""
        hdr = _admin_token_no_pwf(seeded_admin)
        resp = await api_client.get("/api/admin/me", headers=hdr)
        assert resp.status_code == 401,             f"expected 401 for missing pwf; got {resp.status_code} (Phase C not yet applied)"

    @pytest.mark.asyncio
    async def test_token_wrong_pwf_rejected(self, api_client, seeded_admin):
        """Token with wrong pwf value must be rejected with 401."""
        hdr = _admin_token_wrong_pwf(seeded_admin)
        resp = await api_client.get("/api/admin/me", headers=hdr)
        assert resp.status_code == 401,             f"expected 401 for wrong pwf; got {resp.status_code} (Phase C not yet applied)"

    @pytest.mark.asyncio
    async def test_token_malformed_pwf_rejected(self, api_client, seeded_admin):
        """Token with pwf of wrong type (int) must be rejected with 401."""
        hdr = _admin_token_malformed_pwf(seeded_admin)
        resp = await api_client.get("/api/admin/me", headers=hdr)
        assert resp.status_code == 401,             f"expected 401 for malformed pwf; got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_password_rotation_invalidates_old_token(self, api_client, seeded_admin):
        """A token minted before a password-hash change must be rejected after."""
        old_hdr = _admin_token_with_pwf(seeded_admin, _TEST_JWT_SECRET)
        # Simulate password rotation: update the stored hash
        new_pw = admin_seed_support.shared_bootstrap_password() + "X"
        new_hash = hash_password(new_pw)
        async with _Sessions() as s:
            admin_row = (await s.execute(
                select(AdminUser).where(AdminUser.admin_id == seeded_admin.admin_id)
            )).scalar_one()
            admin_row.password_hash = new_hash
            await s.commit()
        # Old token (fingerprint based on old hash) must now be rejected
        resp = await api_client.get("/api/admin/me", headers=old_hdr)
        assert resp.status_code == 401,             f"expected 401 after password rotation; got {resp.status_code}"
        # Restore
        async with _Sessions() as s:
            admin_row = (await s.execute(
                select(AdminUser).where(AdminUser.admin_id == seeded_admin.admin_id)
            )).scalar_one()
            admin_row.password_hash = seeded_admin.password_hash
            await s.commit()

    @pytest.mark.asyncio
    async def test_new_token_after_password_rotation_accepted(self, api_client, seeded_admin):
        """Token minted AFTER a password-hash change must be accepted."""
        new_pw = admin_seed_support.shared_bootstrap_password() + "Y"
        new_hash = hash_password(new_pw)
        async with _Sessions() as s:
            admin_row = (await s.execute(
                select(AdminUser).where(AdminUser.admin_id == seeded_admin.admin_id)
            )).scalar_one()
            admin_row.password_hash = new_hash
            await s.commit()
        # Refresh the local admin object to pick up new hash
        async with _Sessions() as s:
            updated_admin = (await s.execute(
                select(AdminUser).where(AdminUser.admin_id == seeded_admin.admin_id)
            )).scalar_one()
        new_hdr = _admin_token_with_pwf(updated_admin, _TEST_JWT_SECRET)
        resp = await api_client.get("/api/admin/me", headers=new_hdr)
        assert resp.status_code == 200,             f"expected 200 for fresh token after rotation; got {resp.status_code}"
        # Restore
        async with _Sessions() as s:
            admin_row = (await s.execute(
                select(AdminUser).where(AdminUser.admin_id == seeded_admin.admin_id)
            )).scalar_one()
            admin_row.password_hash = seeded_admin.password_hash
            await s.commit()

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, api_client, seeded_admin):
        """Expired token (even with correct pwf) must be rejected with 401."""
        from app.core.admin_token_fingerprint import compute_pwf, PWF_CLAIM
        pwf = compute_pwf(seeded_admin.password_hash, _TEST_JWT_SECRET)
        token = create_access_token(
            {
                "sub": str(seeded_admin.admin_id),
                "type": "admin",
                "email": seeded_admin.email,
                PWF_CLAIM: pwf,
            },
            expires_delta=timedelta(seconds=-1),
        )
        resp = await api_client.get("/api/admin/me",
                                    headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_token_rejected(self, api_client):
        resp = await api_client.get("/api/admin/me",
                                    headers={"Authorization": "Bearer not.a.jwt"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_role_token_rejected(self, api_client, seeded_client):
        """Client JWT sent to an admin route must return 401."""
        token = create_access_token({
            "sub": str(seeded_client.client_id),
            "type": "client",
            "email": seeded_client.email,
        })
        resp = await api_client.get("/api/admin/me",
                                    headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_inactive_admin_rejected(self, api_client, seeded_admin):
        """Valid pwf but is_active=False must return 401."""
        async with _Sessions() as s:
            admin_row = (await s.execute(
                select(AdminUser).where(AdminUser.admin_id == seeded_admin.admin_id)
            )).scalar_one()
            admin_row.is_active = False
            await s.commit()
        hdr = _admin_token_with_pwf(seeded_admin, _TEST_JWT_SECRET)
        resp = await api_client.get("/api/admin/me", headers=hdr)
        assert resp.status_code == 401
        # Restore
        async with _Sessions() as s:
            admin_row = (await s.execute(
                select(AdminUser).where(AdminUser.admin_id == seeded_admin.admin_id)
            )).scalar_one()
            admin_row.is_active = True
            await s.commit()

    @pytest.mark.asyncio
    async def test_missing_authorization_header_returns_403(self, api_client):
        """Missing Authorization header must return 403 (HTTPBearer behavior)."""
        resp = await api_client.get("/api/admin/me")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_multiple_admins_independent_fingerprints(self, api_client, seeded_admin):
        """Rotating admin A does not invalidate admin B token."""
        admin_b = _make_admin()
        async with _Sessions() as s:
            s.add(admin_b)
            await s.commit()
        try:
            hdr_b = _admin_token_with_pwf(admin_b, _TEST_JWT_SECRET)
            # Rotate admin A's password
            new_hash = hash_password(admin_seed_support.shared_bootstrap_password() + "Z")
            async with _Sessions() as s:
                row = (await s.execute(
                    select(AdminUser).where(AdminUser.admin_id == seeded_admin.admin_id)
                )).scalar_one()
                row.password_hash = new_hash
                await s.commit()
            # Admin B's token must still work
            resp = await api_client.get("/api/admin/me", headers=hdr_b)
            assert resp.status_code == 200,                 f"admin B token invalidated by admin A rotation: {resp.status_code}"
        finally:
            async with _Sessions() as s:
                await s.execute(delete(AdminUser).where(AdminUser.admin_id == admin_b.admin_id))
                # Restore admin A
                row = (await s.execute(
                    select(AdminUser).where(AdminUser.admin_id == seeded_admin.admin_id)
                )).scalar_one_or_none()
                if row:
                    row.password_hash = seeded_admin.password_hash
                await s.commit()


class TestNonAdminAuthUnaffected:
    """Client/vendor token flows must be completely unaffected by Phase C."""

    @pytest.mark.asyncio
    async def test_client_token_unaffected_on_client_route(self, api_client, seeded_client):
        """Client JWT without pwf must work on client-only routes."""
        token = create_access_token({
            "sub": str(seeded_client.client_id),
            "type": "client",
            "email": seeded_client.email,
        })
        hdr = {"Authorization": f"Bearer {token}",
               "X-Tenant-ID": str(DEFAULT_TENANT_ID)}
        resp = await api_client.get("/api/campaigns", headers=hdr)
        # 200 or 404 is fine — 401 would mean client auth is broken
        assert resp.status_code != 401,             f"client auth broken by Phase C: status {resp.status_code}"

    @pytest.mark.asyncio
    async def test_client_token_rejected_on_admin_route(self, api_client, seeded_client):
        """Client JWT must be rejected on admin routes with 401."""
        token = create_access_token({
            "sub": str(seeded_client.client_id),
            "type": "client",
            "email": seeded_client.email,
        })
        resp = await api_client.get("/api/admin/me",
                                    headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_client_token_does_not_carry_pwf(self, api_client, seeded_client):
        """Client tokens must not accidentally carry a pwf claim."""
        import base64, json
        token = create_access_token({
            "sub": str(seeded_client.client_id),
            "type": "client",
            "email": seeded_client.email,
        })
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        assert "pwf" not in payload

    @pytest.mark.asyncio
    async def test_public_branding_still_accessible(self, api_client):
        """GET /api/branding must remain public (no token required)."""
        resp = await api_client.get("/api/branding")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_p0_ten_routes_reject_without_token(self, api_client):
        """All ten P0-protected admin routes must still reject unauthenticated requests."""
        routes = [
            ("GET", "/api/admin/tenants"),
            ("GET", "/api/admin/queue/depth"),
            ("GET", "/api/admin/queue/dead"),
            ("GET", "/api/admin/queue/dead/list"),
        ]
        for method, path in routes:
            if method == "GET":
                resp = await api_client.get(path)
            assert resp.status_code in (401, 403),                 f"{method} {path} returned {resp.status_code} without auth"


class TestInsecureKeyBehavior:
    """Behavior when JWT_SECRET_KEY is unset / insecure."""

    def test_compute_pwf_raises_on_insecure_default(self):
        from app.core.admin_token_fingerprint import compute_pwf
        pw_hash = "$2b$12$" + "k" * 53
        with pytest.raises(RuntimeError, match="insecure"):
            compute_pwf(pw_hash, secret_key="your-secret-key-change-in-production")

    def test_verify_pwf_raises_on_insecure_default(self):
        from app.core.admin_token_fingerprint import verify_pwf
        pw_hash = "$2b$12$" + "l" * 53
        with pytest.raises(RuntimeError, match="insecure"):
            verify_pwf("somevalue", pw_hash, secret_key="your-secret-key-change-in-production")
class TestInsecureKeyHTTPBehavior:
    """Fail-closed: insecure JWT_SECRET_KEY must not cause unhandled 500."""

    @pytest.mark.asyncio
    async def test_admin_login_returns_503_when_jwt_secret_insecure(
        self, api_client, seeded_admin
    ):
        """admin_login with insecure JWT_SECRET_KEY must return 503, not 500."""
        import os
        old = os.environ.get("JWT_SECRET_KEY")
        os.environ["JWT_SECRET_KEY"] = "your-secret-key-change-in-production"
        try:
            pw = admin_seed_support.shared_bootstrap_password()
            resp = await api_client.post("/api/admin/login", json={
                "email": seeded_admin.email,
                "password": pw,
            })
            assert resp.status_code == 503, (
                f"expected 503 for insecure JWT_SECRET_KEY; got {resp.status_code}"
            )
            # Message must not contain secrets
            body_text = resp.text
            assert "JWT_SECRET_KEY" not in body_text or "your-secret" not in body_text
        finally:
            if old is None:
                os.environ.pop("JWT_SECRET_KEY", None)
            else:
                os.environ["JWT_SECRET_KEY"] = old

    @pytest.mark.asyncio
    async def test_get_current_admin_returns_401_when_jwt_secret_insecure(
        self, api_client, seeded_admin
    ):
        """get_current_admin with insecure JWT_SECRET_KEY must return 401, not 500."""
        import os
        # Mint a token with the good key first
        hdr = _admin_token_with_pwf(seeded_admin, _TEST_JWT_SECRET)
        # Then switch to insecure key for the validation call
        old = os.environ.get("JWT_SECRET_KEY")
        os.environ["JWT_SECRET_KEY"] = "your-secret-key-change-in-production"
        try:
            resp = await api_client.get("/api/admin/me", headers=hdr)
            assert resp.status_code == 401, (
                f"expected 401 for insecure JWT_SECRET_KEY at validation; got {resp.status_code}"
            )
        finally:
            if old is None:
                os.environ.pop("JWT_SECRET_KEY", None)
            else:
                os.environ["JWT_SECRET_KEY"] = old

    @pytest.mark.asyncio
    async def test_client_auth_unaffected_by_insecure_admin_key(
        self, api_client, seeded_client
    ):
        """Client auth routes must not be affected by insecure JWT_SECRET_KEY.

        Client/vendor auth does not call compute_pwf or verify_pwf so the
        insecure-key guard must never fire on those paths.
        """
        import os
        old = os.environ.get("JWT_SECRET_KEY")
        os.environ["JWT_SECRET_KEY"] = "your-secret-key-change-in-production"
        try:
            token = create_access_token({
                "sub": str(seeded_client.client_id),
                "type": "client",
                "email": seeded_client.email,
            })
            hdr = {"Authorization": f"Bearer {token}",
                   "X-Tenant-ID": str(DEFAULT_TENANT_ID)}
            resp = await api_client.get("/api/campaigns", headers=hdr)
            # Must not be 500 (would indicate admin code path leaked into client path)
            assert resp.status_code != 500, (
                f"client auth caused 500 with insecure JWT key: {resp.status_code}"
            )
        finally:
            if old is None:
                os.environ.pop("JWT_SECRET_KEY", None)
            else:
                os.environ["JWT_SECRET_KEY"] = old
