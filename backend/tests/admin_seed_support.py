"""Shared, self-contained test support for the admin-seed-credential-fix tests.

Spec: .kiro/specs/admin-seed-credential-fix (Phase A, tests first)

Why this exists
---------------
The admin-seed tests need a disposable, provably-isolated PostgreSQL database and a
single, non-secret admin bootstrap password that every test module can share. This
module is the one documented place that provides both, so the Phase B test-literal
removal has exactly one import path to depend on.

It deliberately REUSES the fail-closed guard in ``hotfix_support`` rather than
re-deriving it: importing this module imports ``hotfix_support`` first, whose
import-time ``_validated_test_database_url()`` runs and aborts collection unless
``TEST_DATABASE_URL`` is explicitly set, is a PostgreSQL URL, targets a loopback
host, names a database ending in ``_test``, and the environment does not look like
production (``RENDER`` set, or ``ENVIRONMENT``/``APP_ENV`` = production). The
validated value is re-exported as ``TEST_DATABASE_URL`` (not re-derived here).

Safety properties
-----------------
  * Fail closed via ``hotfix_support``: an unsafe or missing configuration aborts
    collection BEFORE any connection is made.
  * The production ``DATABASE_URL`` is NEVER read, logged or used by this module.
    The engine is built only from the validated ``TEST_DATABASE_URL``.
  * No secrets are embedded. The only password here is a freshly GENERATED
    per-process value (``secrets.token_urlsafe``); neither it nor its hash is ever
    logged or printed. The legacy seed credential is never referenced.
  * Error messages never include a database URL or its password.
  * It does not modify ``hotfix_support.py``, ``conftest.py``, ``app_config.py``,
    ``main.py``, migrations, ``start.sh`` or any production code.
"""
import secrets

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Import the fail-closed validator FIRST so its import-time validation runs and
# collection aborts on any unsafe/missing configuration before we do anything.
# Re-export the already-validated URL instead of re-deriving it here.
from tests import hotfix_support
from tests.hotfix_support import TEST_DATABASE_URL  # noqa: F401  (re-exported)

# The app's own password hasher. Allowed import; used only to hash the generated
# shared password. We never import or read any seed credential or DATABASE_URL.
from app.core.security import hash_password

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

# --- Shared, per-session (per-process) generated admin bootstrap password --------
# Generated exactly once at import time. Process-stable: the same value for every
# test in a run. This is the single documented import path the Phase B test-literal
# removal uses. Never log or print either the password or its hash.
_SHARED_BOOTSTRAP_PASSWORD = secrets.token_urlsafe(18)
_SHARED_BOOTSTRAP_PASSWORD_HASH = hash_password(_SHARED_BOOTSTRAP_PASSWORD)


def shared_bootstrap_password() -> str:
    """Return the process-stable, freshly generated admin bootstrap password.

    Generated once at import via ``secrets.token_urlsafe(18)``. The same value is
    returned for the whole test process. Never log or print this value.
    """
    return _SHARED_BOOTSTRAP_PASSWORD


def shared_bootstrap_password_hash() -> str:
    """Return the bcrypt hash of :func:`shared_bootstrap_password`.

    Hashed with the application's own hasher (``app.core.security.hash_password``)
    so it matches what the running app would accept. Never log or print this value.
    """
    return _SHARED_BOOTSTRAP_PASSWORD_HASH


def make_test_engine():
    """Build a disposable async engine bound to the validated test database.

    Uses ``NullPool`` (mirroring ``hotfix_support``) so no connections linger. The
    engine is built ONLY from ``TEST_DATABASE_URL``; ``DATABASE_URL`` is never read.
    Caller is responsible for ``await engine.dispose()``.
    """
    return create_async_engine(
        TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool
    )


def make_test_sessionmaker(engine=None):
    """Return an ``async_sessionmaker`` bound to a disposable test engine.

    If ``engine`` is None, a fresh engine is created via :func:`make_test_engine`.
    Returns ``(sessionmaker, engine)`` so the caller can dispose the engine.
    """
    if engine is None:
        engine = make_test_engine()
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return sessions, engine


async def assert_isolated_db(conn_or_session) -> None:
    """Assert the connected database is the isolated ``*_test`` DB on loopback.

    Runs ``SELECT current_database()`` through the given connection/session and
    checks the result ends with ``_test``. Separately derives the expected host
    from ``TEST_DATABASE_URL`` (via ``make_url``) and checks it is a loopback host.
    Raises ``AssertionError`` with a clear, URL/password-free message otherwise.
    """
    result = await conn_or_session.execute(text("SELECT current_database()"))
    current_db = result.scalar_one()

    if not isinstance(current_db, str) or not current_db.endswith("_test"):
        raise AssertionError(
            "refusing to run: connected database name does not end in '_test'."
        )

    # Derive host from the validated URL without ever echoing the URL/password.
    host = (make_url(TEST_DATABASE_URL).host or "")
    if host not in _LOOPBACK_HOSTS:
        raise AssertionError(
            "refusing to run: test database host is not a loopback host."
        )


# Columns of admin_users, in a fixed order, for a stable comparable snapshot.
_ADMIN_USER_COLUMNS = (
    "admin_id",
    "email",
    "password_hash",
    "name",
    "is_active",
    "last_login_at",
    "created_at",
    "updated_at",
)


async def snapshot_admin_users(session):
    """Return a stable, comparable snapshot of every ``admin_users`` row.

    Returns a list of dicts (one per row) containing all columns, sorted by
    ``admin_id``, so preservation tests can assert byte/field identity of existing
    rows before and after a bootstrap run. Uses explicit column selection with a
    deterministic ``ORDER BY`` for stability across runs.
    """
    columns_sql = ", ".join(_ADMIN_USER_COLUMNS)
    result = await session.execute(
        text(f"SELECT {columns_sql} FROM admin_users ORDER BY admin_id")
    )
    rows = result.mappings().all()
    return [{col: row[col] for col in _ADMIN_USER_COLUMNS} for row in rows]


def require_admin_bootstrap_module():
    """Import and return ``app.core.admin_bootstrap`` or fail RED-by-absence.

    Until Phase B implements the module, this raises a clear ``AssertionError`` so
    dependent tests fail as RED-by-absence, distinguishable from a harness error.
    """
    try:
        import app.core.admin_bootstrap as admin_bootstrap
    except (ImportError, ModuleNotFoundError):
        raise AssertionError("admin_bootstrap module not implemented") from None
    return admin_bootstrap
