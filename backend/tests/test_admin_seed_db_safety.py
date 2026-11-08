"""Phase A safety test for the admin-seed-credential-fix spec.

Spec: .kiro/specs/admin-seed-credential-fix (Task 5.1, expected PASS)

Purpose
-------
Prove the fail-closed test-DB safety layer refuses unsafe configurations and that
the isolation assertion works. This is a preservation/safety test: it has NO
dependency on the not-yet-built ``admin_bootstrap`` module and is expected to PASS
on the unmodified base.

What is (and is not) exercised
------------------------------
  * The validator-refusal tests call ``hotfix_support._validated_test_database_url``
    directly with a monkeypatched environment. The validator reads ``os.environ`` at
    call time, so patching the process env and calling it is sufficient. These tests
    assert the function RAISES; they NEVER open a database connection.
  * Exactly one test connects: a positive async check that opens the real validated
    ``*_test`` database via ``admin_seed_support.make_test_engine()`` and calls
    ``assert_isolated_db`` to confirm it does not raise and the database name ends in
    ``_test``.
  * A stub-based test confirms ``assert_isolated_db`` raises ``AssertionError`` when a
    connection reports a non-``_test`` ``current_database()``. The stub means no real
    non-test database is ever touched.

Safety / secret hygiene
------------------------
  * Importing ``admin_seed_support`` imports ``hotfix_support`` first, whose
    import-time validator aborts collection unless the real env points at an
    isolated loopback ``*_test`` PostgreSQL database. So this module only collects in
    a safe environment.
  * All URLs used in the refusal tests are CLEARLY FAKE inline values. The real
    committed ``TEST_DATABASE_URL`` and any real credential are never written here.
  * Env patching for production-looking / unsafe values is done INSIDE individual
    test functions via pytest's ``monkeypatch`` (auto-restored per test). We never
    reimport ``admin_seed_support`` or ``hotfix_support`` under a bad env at module
    import time, so collection of the rest of the module is unaffected.
"""
import pytest

# Importing admin_seed_support runs hotfix_support's import-time fail-closed
# validator (collection aborts if the real env is unsafe). We then use the
# module-private validator explicitly: this is a deliberate test of safety behavior.
from tests import admin_seed_support
from tests.hotfix_support import _validated_test_database_url

# --- Clearly FAKE inline URLs (never real; no credential of interest) ------------
# These exist only to drive the validator's refusal branches. They are not real
# endpoints and carry no meaningful password.
_FAKE_NON_LOOPBACK = "postgresql://u:p@db.example.com/foo_test"
_FAKE_BAD_DB_NAME = "postgresql://u:p@127.0.0.1/foo"
_FAKE_NON_PG_SCHEME = "mysql://u:p@127.0.0.1/foo_test"
_FAKE_VALID_SHAPE = "postgresql://u:p@127.0.0.1/foo_test"


# ---------------------------------------------------------------------------------
# 1. Validator refusal tests (no DB connection is opened in any of these).
# ---------------------------------------------------------------------------------


def test_validator_refuses_unset_test_database_url(monkeypatch):
    """Unset TEST_DATABASE_URL -> RuntimeError, no connection."""
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    # Ensure no production-looking vars interfere with this specific assertion.
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(RuntimeError):
        _validated_test_database_url()


def test_validator_refuses_blank_test_database_url(monkeypatch):
    """Blank/whitespace TEST_DATABASE_URL -> RuntimeError, no connection."""
    monkeypatch.setenv("TEST_DATABASE_URL", "   ")
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(RuntimeError):
        _validated_test_database_url()


def test_validator_refuses_non_loopback_host(monkeypatch):
    """Non-loopback host -> RuntimeError, no connection."""
    monkeypatch.setenv("TEST_DATABASE_URL", _FAKE_NON_LOOPBACK)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(RuntimeError):
        _validated_test_database_url()


def test_validator_refuses_db_name_not_ending_test(monkeypatch):
    """Database name not ending in '_test' -> RuntimeError, no connection."""
    monkeypatch.setenv("TEST_DATABASE_URL", _FAKE_BAD_DB_NAME)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(RuntimeError):
        _validated_test_database_url()


def test_validator_refuses_non_postgresql_scheme(monkeypatch):
    """Non-postgresql scheme -> RuntimeError, no connection."""
    monkeypatch.setenv("TEST_DATABASE_URL", _FAKE_NON_PG_SCHEME)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(RuntimeError):
        _validated_test_database_url()


def test_validator_refuses_render_env(monkeypatch):
    """RENDER set -> production-looking env refused, no connection.

    The URL itself is a valid-shape fake, so the ONLY reason to refuse is the
    production-looking environment variable.
    """
    monkeypatch.setenv("TEST_DATABASE_URL", _FAKE_VALID_SHAPE)
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(RuntimeError):
        _validated_test_database_url()


def test_validator_refuses_environment_production(monkeypatch):
    """ENVIRONMENT=production -> refused, no connection."""
    monkeypatch.setenv("TEST_DATABASE_URL", _FAKE_VALID_SHAPE)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(RuntimeError):
        _validated_test_database_url()


def test_validator_refuses_app_env_prod(monkeypatch):
    """APP_ENV=prod -> refused, no connection."""
    monkeypatch.setenv("TEST_DATABASE_URL", _FAKE_VALID_SHAPE)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("APP_ENV", "prod")
    with pytest.raises(RuntimeError):
        _validated_test_database_url()


# ---------------------------------------------------------------------------------
# 2. Positive isolation check (the ONLY test here that opens a DB connection).
# ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assert_isolated_db_passes_on_real_test_db():
    """Under the real validated test env, a live connection is the isolated *_test DB.

    Opens a connection via ``make_test_engine()`` and asserts ``assert_isolated_db``
    does not raise, and that ``current_database()`` ends with ``_test``.
    """
    from sqlalchemy import text

    engine = admin_seed_support.make_test_engine()
    try:
        async with engine.connect() as conn:
            # assert_isolated_db must NOT raise against the validated *_test DB.
            await admin_seed_support.assert_isolated_db(conn)

            # Independently confirm the database name ends with _test.
            current_db = (
                await conn.execute(text("SELECT current_database()"))
            ).scalar_one()
            assert isinstance(current_db, str)
            assert current_db.endswith("_test")
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------------
# 3. Negative isolation check via a lightweight stub (no real non-test DB touched).
# ---------------------------------------------------------------------------------


class _StubResult:
    """Minimal stand-in for a SQLAlchemy Result exposing scalar_one()."""

    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class _StubConnection:
    """Lightweight async connection stub whose current_database() is configurable.

    It implements only what ``assert_isolated_db`` uses: an async ``execute`` that
    returns an object with ``scalar_one()``. No real database is involved.
    """

    def __init__(self, current_database_value):
        self._current_database_value = current_database_value

    async def execute(self, _statement):
        return _StubResult(self._current_database_value)


@pytest.mark.asyncio
async def test_assert_isolated_db_raises_for_non_test_database():
    """A connection reporting a non-'_test' database name must be refused.

    Uses a stub whose ``current_database()`` returns ``'trustcapture'`` (no ``_test``
    suffix) so no real non-test database is touched.
    """
    stub = _StubConnection("trustcapture")
    with pytest.raises(AssertionError):
        await admin_seed_support.assert_isolated_db(stub)
