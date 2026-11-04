"""Shared, self-contained test support for the map/tracking isolation hotfix tests.

Spec: .kiro/specs/map-tracking-isolation-fix (packaging correction, Option B)

Why this exists
---------------
The eight hotfix test files drive real endpoints through the tenant-resolution
middleware. That middleware calls ``app.core.database.get_db()`` directly, so
FastAPI ``dependency_overrides`` do not reach it; it uses the app-runtime
``AsyncSessionLocal``, which is bound at import time to ``DATABASE_URL`` (default:
a non-existent local database). A clean checkout of the production base therefore
returned HTTP 500 ("Error resolving tenant context") for every endpoint test.

This module makes the hotfix tests independent of any other uncommitted test
configuration. It provides, in one place:

  * ``TEST_DATABASE_URL``  - the disposable database, validated FAIL-CLOSED at
                             import time (see ``_validated_test_database_url``).
  * ``DEFAULT_TENANT_ID``  - the default test tenant id (same value the shared
                             conftest uses).
  * ``hotfix_runtime_env`` - an autouse fixture (import it into a test module) that,
                             for each test, (1) points the app-runtime session
                             factory at the validated test database and (2) makes
                             sure the default tenant exists, creating it only if
                             absent and removing it afterwards only if this fixture
                             created it.

Safety properties
-----------------
  * Fail closed: importing this module raises ``RuntimeError`` unless
    ``TEST_DATABASE_URL`` is explicitly set, is a PostgreSQL URL, targets a
    loopback host, and names a database ending in ``_test``. Production-looking
    environments (``RENDER`` set, or ``ENVIRONMENT``/``APP_ENV`` = production)
    are refused outright. Because test modules import this at collection time,
    an unsafe or missing configuration aborts collection BEFORE any fixture
    (including the shared schema drop/create fixture) runs.
  * The production ``DATABASE_URL`` is never read, logged or used. The app-runtime
    session factory is rebound only for the duration of each test and restored
    afterwards, so other test modules are unaffected.
  * No credentials are printed or embedded here; the URL comes from the
    environment only. Error messages never include the URL's password.
  * It does not modify ``conftest.py``, ``app_config.py``, ``main.py``,
    migrations or any W1/W2 test. It composes with the shared ``conftest.py`` when
    present (uses its ``setup_test_database`` fixture for schema creation) and is
    equally valid when that conftest also seeds the default tenant (idempotent).
"""
import os
import uuid
from datetime import datetime, timezone

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Same default tenant id the shared test conftest uses. Duplicated deliberately so
# these tests do not import test configuration that may not be committed.
DEFAULT_TENANT_ID = uuid.UUID("e27c6c7a-7f5b-43df-bdc4-abd76ebb99aa")

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _validated_test_database_url() -> str:
    """Return TEST_DATABASE_URL after fail-closed safety validation."""
    raw = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError(
            "hotfix tests refuse to run: TEST_DATABASE_URL is not set. Point it at a "
            "disposable local PostgreSQL database whose name ends in '_test'."
        )

    if os.environ.get("RENDER") or os.environ.get("ENVIRONMENT", "").lower() in ("production", "prod") \
            or os.environ.get("APP_ENV", "").lower() in ("production", "prod"):
        raise RuntimeError("hotfix tests refuse to run in a production-looking environment.")

    try:
        url = make_url(raw)
    except Exception:  # noqa: BLE001 - never echo the raw value
        raise RuntimeError("hotfix tests refuse to run: TEST_DATABASE_URL is not a valid URL.") from None

    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("hotfix tests refuse to run: TEST_DATABASE_URL must be a PostgreSQL URL.")
    if (url.host or "") not in _LOOPBACK_HOSTS:
        raise RuntimeError(
            f"hotfix tests refuse to run: database host {url.host!r} is not a loopback host."
        )
    if not (url.database or "").endswith("_test"):
        raise RuntimeError(
            f"hotfix tests refuse to run: database name {url.database!r} does not end in '_test'."
        )
    return raw


# Evaluated at import time => collection aborts before any fixture can touch a DB.
TEST_DATABASE_URL = _validated_test_database_url()


@pytest_asyncio.fixture(autouse=True)
async def hotfix_runtime_env(setup_test_database):
    """Per-test: bind the app-runtime session factory to the test DB and ensure the
    default tenant exists. ``setup_test_database`` (shared conftest) creates tables.
    """
    import app.core.database as appdb
    from app.models.tenant_config import TenantConfig

    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool)
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    original_factory = appdb.AsyncSessionLocal
    appdb.AsyncSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False,
    )

    created = False
    try:
        async with sessions() as s:
            existing = (await s.execute(
                select(TenantConfig.tenant_id).where(TenantConfig.tenant_id == DEFAULT_TENANT_ID)
            )).scalar_one_or_none()
            if existing is None:
                now = datetime.now(tz=timezone.utc)
                s.add(TenantConfig(
                    tenant_id=DEFAULT_TENANT_ID,
                    tenant_name="Test Tenant",
                    subdomain="default",
                    primary_color="#007bff",
                    secondary_color="#6c757d",
                    email_from_address="noreply@test.trustcapture.com",
                    email_from_name="TrustCapture Test",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ))
                await s.commit()
                created = True
        yield
    finally:
        appdb.AsyncSessionLocal = original_factory
        try:
            if created:
                async with sessions() as s:
                    await s.execute(delete(TenantConfig).where(TenantConfig.tenant_id == DEFAULT_TENANT_ID))
                    await s.commit()
        finally:
            await engine.dispose()
