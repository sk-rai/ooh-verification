"""Phase A CONCURRENCY contract tests for the admin-seed-credential-fix spec.

Spec: .kiro/specs/admin-seed-credential-fix (Task 5.4, RED-by-absence until Phase B)

What this module specifies
--------------------------
The Phase B concurrency behaviour of ``app.core.admin_bootstrap.bootstrap_admin``
described in design.md Section B ("Concurrency-safe empty-table bootstrap"):

    bootstrap_admin(session, email, password_hash, logger) -> Outcome

Correctness Property 3 (design.md): *for any* number of simultaneous bootstrap
executions against an EMPTY ``admin_users`` table - with identical OR with differing
emails - the fixed seed step SHALL create AT MOST ONE row, and a racing duplicate
insert SHALL map to the non-fatal ``ALREADY_EXISTS``, never ``BOOTSTRAP_DB_ERROR``.
This is guaranteed by a transaction-scoped advisory lock plus an emptiness recheck
inside the lock, with the UNIQUE email constraint as a second line of defence.

    Validates: Requirements 2.2, 2.4, 3.1

RED-by-absence (do not weaken)
------------------------------
The module ``app.core.admin_bootstrap`` DOES NOT EXIST YET. Every test here calls
``admin_seed_support.require_admin_bootstrap_module()`` as the FIRST statement of its
body, which raises ``AssertionError('admin_bootstrap module not implemented')`` while
the module is absent. So every test FAILS with that uniform, greppable signal -
distinguishable from a collection/harness error. The not-yet-existing module is
imported lazily inside test bodies ONLY (never at module top) so ``--collect-only``
always succeeds. Do NOT implement the module to make these pass - that is Phase B.

The concurrency driver is placed AFTER the absence guard in each test, so once Phase
B exists the test becomes meaningful: real ``asyncio.gather`` over SEPARATE sessions,
each from its own connection, exercises the advisory-lock + recheck race.

Secret hygiene
--------------
Every supplied hash comes from ``admin_seed_support.shared_bootstrap_password_hash()``
- a freshly GENERATED per-process value, never a literal and never the legacy seed
credential. No secret value is written to this file. The platform email
``admin@trustcapture.com`` is already public and non-secret.

Safety
------
Importing ``admin_seed_support`` imports ``hotfix_support`` first, whose import-time
fail-closed validator aborts collection unless the real env points at an isolated
loopback ``*_test`` PostgreSQL database. Each test asserts isolation via
``assert_isolated_db`` before touching data, arranges an EMPTY table, and cleans up
afterward. Every concurrent worker uses its OWN session/connection (required for a
real DB-level race) created from ``admin_seed_support.make_test_sessionmaker()``.
"""
import asyncio
import logging

import pytest
from sqlalchemy import text

# The ONLY project import at module top. Importing admin_seed_support runs
# hotfix_support's import-time fail-closed validator, so this module only collects in
# a safe, isolated *_test environment. The module under test is imported lazily inside
# each test body via require_admin_bootstrap_module() so --collect-only always works.
from tests import admin_seed_support

# Already-public, non-secret platform admin address. Not a credential.
_PUBLIC_ADMIN_EMAIL = "admin@trustcapture.com"

# The RED-by-absence signal every test in this module must surface until Phase B.
_ABSENCE_MESSAGE = "admin_bootstrap module not implemented"

_LOGGER = logging.getLogger("admin_bootstrap_concurrency_test")


# =====================================================================================
# Small DB helpers (no dependency on the module under test).
# =====================================================================================


async def _delete_all_admins(session) -> None:
    await session.execute(text("DELETE FROM admin_users"))
    await session.commit()


async def _count_admins(session) -> int:
    result = await session.execute(text("SELECT COUNT(*) FROM admin_users"))
    return int(result.scalar_one())


def _status_text(outcome) -> str:
    """Return a greppable status token for an Outcome, tolerant of its exact shape.

    The Phase B module may model Outcome as an Enum, a str, or an object exposing
    ``status``/``code``/``name``/``value``. We normalise to a string containing the
    status token without over-constraining the type.
    """
    for attr in ("status", "code", "name", "value"):
        value = getattr(outcome, attr, None)
        if isinstance(value, str) and value:
            return value
    return str(outcome)


async def _run_concurrent_bootstraps(sessions_factory, emails):
    """Drive N concurrent bootstrap_admin calls, one per fresh session/connection.

    ``sessions_factory`` is an ``async_sessionmaker``. For each email a SEPARATE
    session (hence a separate connection) is opened and a bootstrap call is scheduled;
    all calls run concurrently via ``asyncio.gather``. Returns the list of status
    tokens in the same order as ``emails``. Each worker owns and closes its session.
    """
    supplied_hash = admin_seed_support.shared_bootstrap_password_hash()  # GENERATED

    async def _worker(email):
        admin_bootstrap = admin_seed_support.require_admin_bootstrap_module()
        async with sessions_factory() as session:
            outcome = await admin_bootstrap.bootstrap_admin(
                session, email=email, password_hash=supplied_hash, logger=_LOGGER
            )
            return _status_text(outcome)

    results = await asyncio.gather(*(_worker(email) for email in emails))
    return list(results)


# =====================================================================================
# Fixture: a provably isolated, EMPTY admin_users table, with its own disposable
# engine + sessionmaker so concurrent workers get independent connections.
# =====================================================================================


@pytest.fixture
async def empty_table_sessionmaker(setup_test_database):
    """Yield an ``async_sessionmaker`` over a provably isolated, EMPTY admin_users table.

    ``setup_test_database`` (session fixture, conftest) guarantees the schema exists.
    The fixture asserts isolation via ``assert_isolated_db`` and empties the table
    before yielding the sessionmaker, then cleans up and disposes the engine. The
    sessionmaker (not a single session) is yielded on purpose so each concurrent
    worker can open its OWN session/connection for a real race.
    """
    sessions, engine = admin_seed_support.make_test_sessionmaker()
    try:
        async with sessions() as session:
            await admin_seed_support.assert_isolated_db(session)
            await _delete_all_admins(session)
            assert await _count_admins(session) == 0, (
                "harness: admin_users was not empty after cleanup before the test"
            )
        yield sessions
    finally:
        try:
            async with sessions() as session:
                await _delete_all_admins(session)
        finally:
            await engine.dispose()


# =====================================================================================
# Concurrency contract tests. Each is RED-by-absence until Phase B.
# =====================================================================================


async def test_two_concurrent_same_email_create_exactly_one(empty_table_sessionmaker):
    """Two concurrent calls, SAME email, empty table -> exactly one row.

    Exactly one caller returns ADMIN_CREATED and the other ALREADY_EXISTS (either
    ordering is acceptable), and neither returns BOOTSTRAP_DB_ERROR. The advisory
    lock + emptiness recheck (with the UNIQUE email constraint as a backstop) ensure
    the racing duplicate insert is non-fatal.

    Validates: Requirements 2.2, 2.4, 3.1
    """
    # RED-by-absence: fails here with AssertionError(_ABSENCE_MESSAGE) until Phase B.
    admin_seed_support.require_admin_bootstrap_module()

    statuses = await _run_concurrent_bootstraps(
        empty_table_sessionmaker, [_PUBLIC_ADMIN_EMAIL, _PUBLIC_ADMIN_EMAIL]
    )

    # Exactly one row exists afterward.
    async with empty_table_sessionmaker() as verify_session:
        assert await _count_admins(verify_session) == 1

    # Never a fatal DB error.
    assert all("BOOTSTRAP_DB_ERROR" not in status for status in statuses)
    # Exactly one creator and one loser, in either order.
    created = [s for s in statuses if "ADMIN_CREATED" in s]
    already = [s for s in statuses if "ALREADY_EXISTS" in s]
    assert len(created) == 1, f"expected exactly one ADMIN_CREATED, got {statuses!r}"
    assert len(already) == 1, f"expected exactly one ALREADY_EXISTS, got {statuses!r}"


async def test_two_concurrent_differing_emails_create_exactly_one(empty_table_sessionmaker):
    """Two concurrent calls, DIFFERING emails, empty table -> exactly one row.

    The advisory lock + emptiness recheck guarantee AT MOST ONE admin is created even
    when the two racing callers supply different emails; the loser returns
    ALREADY_EXISTS and never BOOTSTRAP_DB_ERROR.

    Validates: Requirements 2.2, 2.4, 3.1
    """
    # RED-by-absence: fails here with AssertionError(_ABSENCE_MESSAGE) until Phase B.
    admin_seed_support.require_admin_bootstrap_module()

    statuses = await _run_concurrent_bootstraps(
        empty_table_sessionmaker,
        ["first@trustcapture.com", "second@trustcapture.com"],
    )

    # Exactly one row exists afterward (at most one, and at least one creator ran).
    async with empty_table_sessionmaker() as verify_session:
        assert await _count_admins(verify_session) == 1

    assert all("BOOTSTRAP_DB_ERROR" not in status for status in statuses)
    created = [s for s in statuses if "ADMIN_CREATED" in s]
    already = [s for s in statuses if "ALREADY_EXISTS" in s]
    assert len(created) == 1, f"expected exactly one ADMIN_CREATED, got {statuses!r}"
    assert len(already) == 1, (
        f"the loser must return ALREADY_EXISTS, got {statuses!r}"
    )


async def test_n_concurrent_same_email_create_exactly_one(empty_table_sessionmaker):
    """N concurrent calls (N=5), SAME email, empty table -> exactly one row.

    All-but-one caller returns ALREADY_EXISTS; exactly one returns ADMIN_CREATED; no
    exception and no BOOTSTRAP_DB_ERROR under the wider race.

    Validates: Requirements 2.2, 2.4, 3.1
    """
    # RED-by-absence: fails here with AssertionError(_ABSENCE_MESSAGE) until Phase B.
    admin_seed_support.require_admin_bootstrap_module()

    n = 5
    statuses = await _run_concurrent_bootstraps(
        empty_table_sessionmaker, [_PUBLIC_ADMIN_EMAIL] * n
    )

    # Exactly one row exists afterward.
    async with empty_table_sessionmaker() as verify_session:
        assert await _count_admins(verify_session) == 1

    assert all("BOOTSTRAP_DB_ERROR" not in status for status in statuses)
    created = [s for s in statuses if "ADMIN_CREATED" in s]
    already = [s for s in statuses if "ALREADY_EXISTS" in s]
    assert len(created) == 1, f"expected exactly one ADMIN_CREATED across N, got {statuses!r}"
    assert len(already) == n - 1, (
        f"expected N-1 ALREADY_EXISTS across N={n}, got {statuses!r}"
    )
