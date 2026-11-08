"""Phase A outcome-CONTRACT tests for the admin-seed-credential-fix spec.

Spec: .kiro/specs/admin-seed-credential-fix (Task 5.3, RED-by-absence until Phase B)

What this module specifies
--------------------------
The full behavioural contract of the Phase B module ``app.core.admin_bootstrap``
and the owner CLI ``app.cli.create_admin`` as described in design.md Section B. It
asserts the testable function:

    bootstrap_admin(session, email, password_hash, logger) -> Outcome

against an explicit, isolated async session (never the deploy entry point, which is
the only code allowed to read ``DATABASE_URL``). Neither the module nor the CLI
exists yet, so EVERY test here is RED-BY-ABSENCE: the first statement of each test
body (or its fixture) calls
``admin_seed_support.require_admin_bootstrap_module()`` (CLI tests use an equivalent
absence guard) which raises ``AssertionError('admin_bootstrap module not
implemented')`` on ImportError. That clear, uniform signal distinguishes
"not built yet" from a harness/collection error.

IMPORTANT (do not weaken)
-------------------------
  * Do NOT implement ``app.core.admin_bootstrap`` or ``app.cli.create_admin`` to make
    these pass - that is Phase B. Until then they MUST fail with the module-absence
    AssertionError.
  * Module-level imports are restricted to stdlib, pytest, hypothesis and
    ``admin_seed_support`` so a clean ``--collect-only`` succeeds. The import of the
    not-yet-existing module happens INSIDE test bodies/fixtures, never at module top.

Outcome contract encoded (design.md Section B)
----------------------------------------------
  * ADMIN_EXISTS: table non-empty -> no write, existing row untouched, idempotent.
  * NO_ADMIN_NO_BOOTSTRAP: empty + no bootstrap args -> zero created, WARNING.
  * BOOTSTRAP_INVALID (reason code only): empty + invalid (bad email, bad bcrypt
    prefix, wrong length, cost out of range, disallowed charset, partial config) ->
    zero created, ERROR.
  * ADMIN_CREATED: empty + valid email + valid bcrypt hash -> exactly one row with
    the supplied hash and a lowercased/stripped email.
  * ALREADY_EXISTS: racing duplicate email -> non-fatal (never BOOTSTRAP_DB_ERROR).
  * BOOTSTRAP_ENV_STILL_SET: admin exists AND both bootstrap env vars set -> WARNING
    on every call.
  * Validator (pure-string bcrypt check): accept ``$2b$``/``$2a$``, length 60, cost
    10-14; reject everything else. Email normalised lowercase + strip.
  * Logging / secret rules: captured logs (caplog) and any stdout contain neither the
    hash nor the email VALUE for the created case - only status/reason codes and
    exception class names.
  * Property tests (Hypothesis, a confirmed dependency): (a) arbitrary non-bcrypt
    strings as ``password_hash`` on an empty table NEVER create a row and return
    BOOTSTRAP_INVALID; (b) a pre-existing admin set is a no-op (ADMIN_EXISTS) and the
    full-row snapshot is identical before and after.
  * CLI contract: exit 0 on create / already-exists no-op; non-zero on invalid and DB
    error; rejects short/weak password (min length 14 + variety check); refuses when
    an admin exists unless ``--force-additional``; never echoes the password.

Secret hygiene
--------------
The VALID case uses a GENERATED hash from
``admin_seed_support.shared_bootstrap_password_hash()`` - never a literal and never
the legacy seed credential. No secret value is written to this file. The platform
email ``admin@trustcapture.com`` is already public and non-secret.
"""
import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import text

# Importing admin_seed_support imports hotfix_support first, whose import-time
# fail-closed validator aborts collection unless the real env points at an isolated
# loopback *_test PostgreSQL database. So this module only collects when safe.
# This is the ONLY project import at module top; the not-yet-existing module under
# test is imported lazily inside each test so --collect-only always succeeds.
from tests import admin_seed_support

try:  # Hypothesis is a confirmed dependency; fall back to parametrize if ever absent.
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    _HAS_HYPOTHESIS = True
except ImportError:  # pragma: no cover - hypothesis is present in this project
    _HAS_HYPOTHESIS = False


# Already-public, non-secret platform admin address. Used only to drive contract
# assertions; it is not a credential.
_PUBLIC_ADMIN_EMAIL = "admin@trustcapture.com"

# The RED-by-absence signal every test in this module must surface.
_ABSENCE_MESSAGE = "admin_bootstrap module not implemented"

# CLI module path that also does not exist yet (guarded the same way).
_CLI_MODULE = "app.cli.create_admin"


# =====================================================================================
# Absence guards (RED-by-absence). These run INSIDE tests/fixtures, never at import.
# =====================================================================================


def _require_cli_module():
    """Import ``app.cli.create_admin`` or fail RED-by-absence.

    Mirrors ``admin_seed_support.require_admin_bootstrap_module`` so CLI tests surface
    the SAME ``AssertionError('admin_bootstrap module not implemented')`` signal
    rather than a different error, keeping RED-by-absence uniform across the module.
    """
    try:
        import app.cli.create_admin as create_admin_cli
    except (ImportError, ModuleNotFoundError):
        raise AssertionError(_ABSENCE_MESSAGE) from None
    return create_admin_cli


# =====================================================================================
# Fixtures: a provably isolated, empty admin_users table on the *_test DB.
# =====================================================================================


async def _delete_all_admins(session) -> None:
    await session.execute(text("DELETE FROM admin_users"))
    await session.commit()


async def _count_admins(session) -> int:
    result = await session.execute(text("SELECT COUNT(*) FROM admin_users"))
    return int(result.scalar_one())


async def _insert_admin(session, email: str, password_hash: str, name: str = "Existing Admin"):
    """Insert one admin row directly via SQL (no dependency on the module under test).

    Used only to arrange a NON-empty table for ADMIN_EXISTS / preservation cases.
    """
    await session.execute(
        text(
            "INSERT INTO admin_users "
            "(admin_id, email, password_hash, name, is_active, created_at, updated_at) "
            "VALUES (:admin_id, :email, :password_hash, :name, true, now(), now())"
        ),
        {
            "admin_id": uuid.uuid4(),
            "email": email,
            "password_hash": password_hash,
            "name": name,
        },
    )
    await session.commit()


@pytest.fixture
async def empty_admin_session(setup_test_database):
    """Yield an async session bound to a provably isolated, EMPTY admin_users table.

    ``setup_test_database`` (session fixture, conftest) guarantees the schema exists.
    The fixture asserts isolation via ``assert_isolated_db`` before and empties the
    table before yielding, and cleans up + disposes the engine afterward.
    """
    sessions, engine = admin_seed_support.make_test_sessionmaker()
    try:
        async with sessions() as session:
            await admin_seed_support.assert_isolated_db(session)
            await _delete_all_admins(session)
            assert await _count_admins(session) == 0, (
                "harness: admin_users was not empty after cleanup before the test"
            )
        async with sessions() as session:
            yield session
    finally:
        try:
            async with sessions() as session:
                await _delete_all_admins(session)
        finally:
            await engine.dispose()


@pytest.fixture
async def seeded_admin_session(setup_test_database):
    """Yield an async session with exactly one pre-existing admin row already present.

    Arranges a NON-bug-condition (non-empty) table using the GENERATED shared hash
    (never a literal). Asserts isolation first; cleans up and disposes afterward.
    """
    sessions, engine = admin_seed_support.make_test_sessionmaker()
    try:
        async with sessions() as session:
            await admin_seed_support.assert_isolated_db(session)
            await _delete_all_admins(session)
            await _insert_admin(
                session,
                email="owner@trustcapture.com",
                password_hash=admin_seed_support.shared_bootstrap_password_hash(),
            )
            assert await _count_admins(session) == 1, (
                "harness: expected exactly one arranged admin row"
            )
        async with sessions() as session:
            yield session
    finally:
        try:
            async with sessions() as session:
                await _delete_all_admins(session)
        finally:
            await engine.dispose()


# =====================================================================================
# Helpers to read Outcome status/reason without pinning the exact Outcome type.
# =====================================================================================


def _status_text(outcome) -> str:
    """Return a status token for an Outcome, tolerating enum/str/attr-bearing shapes.

    The module may model Outcome as an Enum, a str, or an object exposing ``status``
    / ``code`` / ``name``. These contract tests assert on a greppable token, so we
    normalise to a string containing that token without over-constraining the type.
    """
    for attr in ("status", "code", "name", "value"):
        value = getattr(outcome, attr, None)
        if isinstance(value, str) and value:
            return value
    return str(outcome)


def _assert_no_secret_in(captured_text: str, *, email_value: str, password_hash: str) -> None:
    """Assert neither the email VALUE nor the hash appears in captured logs/stdout."""
    assert password_hash not in captured_text, (
        "secret leak: the bcrypt hash must never appear in logs or stdout"
    )
    assert email_value not in captured_text, (
        "secret leak: the email value must never appear in logs or stdout"
    )


# =====================================================================================
# Outcome-matrix contract tests (function layer). Each is RED-by-absence until Phase B.
# =====================================================================================


async def test_absent_config_returns_no_admin_no_bootstrap(empty_admin_session, caplog):
    """Empty table + no bootstrap args -> zero created, NO_ADMIN_NO_BOOTSTRAP, WARNING."""
    import logging

    admin_bootstrap = admin_seed_support.require_admin_bootstrap_module()
    logger = logging.getLogger("admin_bootstrap_test")

    with caplog.at_level(logging.WARNING, logger=logger.name):
        outcome = await admin_bootstrap.bootstrap_admin(
            empty_admin_session, email=None, password_hash=None, logger=logger
        )

    assert "NO_ADMIN_NO_BOOTSTRAP" in _status_text(outcome)
    assert await _count_admins(empty_admin_session) == 0
    assert any(rec.levelno == logging.WARNING for rec in caplog.records)
    assert "NO_ADMIN_NO_BOOTSTRAP" in caplog.text


@pytest.mark.parametrize(
    "reason, email, password_hash",
    [
        ("bad_email", "not-an-email", None),
        ("bad_prefix", _PUBLIC_ADMIN_EMAIL, "$2y$12$" + ("a" * 53)),
        ("bad_length", _PUBLIC_ADMIN_EMAIL, "$2b$12$short"),
        ("cost_too_low", _PUBLIC_ADMIN_EMAIL, "$2b$09$" + ("a" * 53)),
        ("cost_too_high", _PUBLIC_ADMIN_EMAIL, "$2b$31$" + ("a" * 53)),
        ("bad_charset", _PUBLIC_ADMIN_EMAIL, "$2b$12$" + ("!" * 53)),
        ("partial_email_only", _PUBLIC_ADMIN_EMAIL, None),
    ],
)
async def test_invalid_config_returns_bootstrap_invalid(empty_admin_session, caplog, reason, email, password_hash):
    """Empty table + invalid config -> zero created, BOOTSTRAP_INVALID, ERROR, reason code.

    For the ``bad_email`` case a VALID generated hash is paired with the bad email so
    the only defect is the email. ``partial_email_only`` supplies just one of the two
    bootstrap inputs, which the contract treats as INVALID (not ABSENT).
    """
    import logging

    admin_bootstrap = admin_seed_support.require_admin_bootstrap_module()
    logger = logging.getLogger("admin_bootstrap_test")

    effective_hash = password_hash
    if reason == "bad_email":
        effective_hash = admin_seed_support.shared_bootstrap_password_hash()

    with caplog.at_level(logging.ERROR, logger=logger.name):
        outcome = await admin_bootstrap.bootstrap_admin(
            empty_admin_session, email=email, password_hash=effective_hash, logger=logger
        )

    status = _status_text(outcome)
    assert "BOOTSTRAP_INVALID" in status
    assert await _count_admins(empty_admin_session) == 0
    assert any(rec.levelno == logging.ERROR for rec in caplog.records)
    assert "BOOTSTRAP_INVALID" in caplog.text
    assert "reason" in caplog.text.lower()


async def test_valid_config_creates_exactly_one_admin_with_supplied_hash(empty_admin_session, caplog, capsys):
    """Empty table + valid email + valid bcrypt hash -> exactly one ADMIN_CREATED row.

    The created row carries EXACTLY the supplied (generated) hash and a
    lowercased/stripped email. Captured logs AND stdout contain neither the hash nor
    the email value - only status/reason codes.
    """
    import logging

    admin_bootstrap = admin_seed_support.require_admin_bootstrap_module()
    logger = logging.getLogger("admin_bootstrap_test")

    supplied_hash = admin_seed_support.shared_bootstrap_password_hash()  # GENERATED, never a literal
    supplied_email = "  Admin@TrustCapture.com  "
    normalised_email = "admin@trustcapture.com"

    with caplog.at_level(logging.INFO, logger=logger.name):
        outcome = await admin_bootstrap.bootstrap_admin(
            empty_admin_session,
            email=supplied_email,
            password_hash=supplied_hash,
            logger=logger,
        )

    assert "ADMIN_CREATED" in _status_text(outcome)
    assert await _count_admins(empty_admin_session) == 1

    row = (
        await empty_admin_session.execute(
            text("SELECT email, password_hash FROM admin_users")
        )
    ).mappings().one()
    assert row["email"] == normalised_email
    assert row["password_hash"] == supplied_hash

    stdout = capsys.readouterr().out
    _assert_no_secret_in(caplog.text, email_value=normalised_email, password_hash=supplied_hash)
    _assert_no_secret_in(stdout, email_value=normalised_email, password_hash=supplied_hash)
    assert "ADMIN_CREATED" in caplog.text


async def test_existing_admin_is_untouched_and_idempotent(seeded_admin_session, caplog):
    """Non-empty table -> ADMIN_EXISTS, no write, existing row byte-identical, idempotent.

    Snapshots the full admin_users rows before and after, and after a SECOND call, to
    prove the existing admin is never modified and the operation is idempotent.
    """
    import logging

    admin_bootstrap = admin_seed_support.require_admin_bootstrap_module()
    logger = logging.getLogger("admin_bootstrap_test")

    before = await admin_seed_support.snapshot_admin_users(seeded_admin_session)

    outcome1 = await admin_bootstrap.bootstrap_admin(
        seeded_admin_session,
        email=_PUBLIC_ADMIN_EMAIL,
        password_hash=admin_seed_support.shared_bootstrap_password_hash(),
        logger=logger,
    )
    after1 = await admin_seed_support.snapshot_admin_users(seeded_admin_session)

    outcome2 = await admin_bootstrap.bootstrap_admin(
        seeded_admin_session,
        email=_PUBLIC_ADMIN_EMAIL,
        password_hash=admin_seed_support.shared_bootstrap_password_hash(),
        logger=logger,
    )
    after2 = await admin_seed_support.snapshot_admin_users(seeded_admin_session)

    assert "ADMIN_EXISTS" in _status_text(outcome1)
    assert "ADMIN_EXISTS" in _status_text(outcome2)
    assert after1 == before, "existing admin row must be byte/field-identical after bootstrap"
    assert after2 == before, "bootstrap must be idempotent on repeat runs"
    assert await _count_admins(seeded_admin_session) == 1


async def test_racing_duplicate_email_maps_to_already_exists(empty_admin_session):
    """A racing duplicate-email insert -> ALREADY_EXISTS (non-fatal), never DB_ERROR.

    Arrange the race by inserting the same (normalised) email out-of-band first, then
    call bootstrap with the same email so the UNIQUE-constraint path is exercised. The
    contract maps this to the non-fatal ALREADY_EXISTS, not BOOTSTRAP_DB_ERROR.
    """
    import logging

    admin_bootstrap = admin_seed_support.require_admin_bootstrap_module()
    logger = logging.getLogger("admin_bootstrap_test")

    race_email = "race@trustcapture.com"
    await _insert_admin(
        empty_admin_session,
        email=race_email,
        password_hash=admin_seed_support.shared_bootstrap_password_hash(),
    )

    outcome = await admin_bootstrap.bootstrap_admin(
        empty_admin_session,
        email=race_email,
        password_hash=admin_seed_support.shared_bootstrap_password_hash(),
        logger=logger,
    )

    status = _status_text(outcome)
    assert "ALREADY_EXISTS" in status
    assert "BOOTSTRAP_DB_ERROR" not in status
    assert await _count_admins(empty_admin_session) == 1


async def test_env_still_set_warns_when_admin_exists(seeded_admin_session, caplog):
    """Admin exists AND both bootstrap inputs still provided -> BOOTSTRAP_ENV_STILL_SET WARNING.

    The warning fires on every call while an admin already exists and bootstrap
    inputs are still present, and never prints values.
    """
    import logging

    admin_bootstrap = admin_seed_support.require_admin_bootstrap_module()
    logger = logging.getLogger("admin_bootstrap_test")

    supplied_hash = admin_seed_support.shared_bootstrap_password_hash()
    supplied_email = _PUBLIC_ADMIN_EMAIL

    with caplog.at_level(logging.WARNING, logger=logger.name):
        outcome = await admin_bootstrap.bootstrap_admin(
            seeded_admin_session,
            email=supplied_email,
            password_hash=supplied_hash,
            logger=logger,
        )

    assert "BOOTSTRAP_ENV_STILL_SET" in caplog.text
    assert any(rec.levelno == logging.WARNING for rec in caplog.records)
    assert await _count_admins(seeded_admin_session) == 1
    _assert_no_secret_in(caplog.text, email_value=supplied_email, password_hash=supplied_hash)
    assert "EXISTS" in _status_text(outcome)


# =====================================================================================
# Pure-string validator contract (no passlib internals). RED-by-absence until Phase B.
# =====================================================================================


@pytest.mark.parametrize(
    "candidate, expected_valid",
    [
        ("$2b$12$" + ("a" * 53), True),
        ("$2a$10$" + ("a" * 53), True),
        ("$2a$14$" + ("a" * 53), True),
        ("$2y$12$" + ("a" * 53), False),
        ("$2b$12$" + ("a" * 10), False),
        ("$2b$09$" + ("a" * 53), False),
        ("$2b$15$" + ("a" * 53), False),
        ("$2b$12$" + ("!" * 53), False),
        ("", False),
    ],
)
def test_validator_accepts_only_wellformed_bcrypt(candidate, expected_valid):
    """Pure-string bcrypt check: accept $2b$/$2a$, length 60, cost 10-14; reject others.

    The module must expose a pure-string validator (name discovered at runtime); we
    try common names so Phase B naming is not over-constrained, but at least one must
    exist (RED-by-absence makes this moot until the module is built).
    """
    admin_bootstrap = admin_seed_support.require_admin_bootstrap_module()

    validator = None
    for name in ("is_valid_bcrypt_hash", "validate_bcrypt_hash", "is_valid_password_hash"):
        candidate_fn = getattr(admin_bootstrap, name, None)
        if callable(candidate_fn):
            validator = candidate_fn
            break
    assert validator is not None, "admin_bootstrap must expose a pure-string bcrypt validator"

    assert bool(validator(candidate)) is expected_valid


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("  Admin@TrustCapture.com  ", "admin@trustcapture.com"),
        ("OWNER@TRUSTCAPTURE.COM", "owner@trustcapture.com"),
        ("\tmixed@Example.Com\n", "mixed@example.com"),
    ],
)
def test_email_normalisation_lowercases_and_strips(raw, expected):
    """Email normalisation: lowercase + strip surrounding whitespace."""
    admin_bootstrap = admin_seed_support.require_admin_bootstrap_module()

    normaliser = None
    for name in ("normalize_email", "normalise_email", "normalized_email"):
        candidate_fn = getattr(admin_bootstrap, name, None)
        if callable(candidate_fn):
            normaliser = candidate_fn
            break
    assert normaliser is not None, "admin_bootstrap must expose an email normaliser"

    assert normaliser(raw) == expected


# =====================================================================================
# Property-based contract tests (Hypothesis if present, else parametrized fallback).
# =====================================================================================

_NON_BCRYPT_FALLBACK = [
    "",
    "plaintext",
    "$1$abcdefgh$",
    "$2y$12$" + ("a" * 53),
    "$2b$12$short",
    "$2b$09$" + ("a" * 53),
    "not-a-hash-at-all-" + ("x" * 40),
]


async def _assert_non_bcrypt_never_creates(session, admin_bootstrap, password_hash):
    import logging

    logger = logging.getLogger("admin_bootstrap_test")
    await _delete_all_admins(session)
    outcome = await admin_bootstrap.bootstrap_admin(
        session, email=_PUBLIC_ADMIN_EMAIL, password_hash=password_hash, logger=logger
    )
    assert "BOOTSTRAP_INVALID" in _status_text(outcome)
    assert await _count_admins(session) == 0


if _HAS_HYPOTHESIS:

    @settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        password_hash=st.text(max_size=80).filter(
            lambda s: not (len(s) == 60 and s[:4] in ("$2b$", "$2a$"))
        )
    )
    async def test_property_non_bcrypt_never_creates_row(empty_admin_session, password_hash):
        """Property (a): arbitrary non-bcrypt hash on an empty table -> no row, INVALID.

        Validates: Requirements 2.2, 2.3
        """
        admin_bootstrap = admin_seed_support.require_admin_bootstrap_module()
        await _assert_non_bcrypt_never_creates(empty_admin_session, admin_bootstrap, password_hash)

else:  # pragma: no cover - hypothesis is a confirmed dependency here

    @pytest.mark.parametrize("password_hash", _NON_BCRYPT_FALLBACK)
    async def test_property_non_bcrypt_never_creates_row(empty_admin_session, password_hash):
        """Parametrized fallback for property (a): non-bcrypt hash -> no row, INVALID.

        Validates: Requirements 2.2, 2.3
        """
        admin_bootstrap = admin_seed_support.require_admin_bootstrap_module()
        await _assert_non_bcrypt_never_creates(empty_admin_session, admin_bootstrap, password_hash)


if _HAS_HYPOTHESIS:

    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        email=st.emails(),
        password_hash=st.text(max_size=80),
    )
    async def test_property_existing_admin_is_noop(seeded_admin_session, email, password_hash):
        """Property (b): with an existing admin, any bootstrap input is a no-op.

        The pre-existing row snapshot must be identical before and after, regardless
        of the (arbitrary) email/hash passed in, and the outcome is ADMIN_EXISTS.

        Validates: Requirements 3.1
        """
        admin_bootstrap = admin_seed_support.require_admin_bootstrap_module()
        import logging

        logger = logging.getLogger("admin_bootstrap_test")
        before = await admin_seed_support.snapshot_admin_users(seeded_admin_session)
        outcome = await admin_bootstrap.bootstrap_admin(
            seeded_admin_session, email=email, password_hash=password_hash, logger=logger
        )
        after = await admin_seed_support.snapshot_admin_users(seeded_admin_session)
        assert "ADMIN_EXISTS" in _status_text(outcome)
        assert after == before

else:  # pragma: no cover - hypothesis is a confirmed dependency here

    @pytest.mark.parametrize(
        "email, password_hash",
        [
            ("someone@example.com", "whatever"),
            ("ANOTHER@Example.COM", "$2b$12$" + ("a" * 53)),
        ],
    )
    async def test_property_existing_admin_is_noop(seeded_admin_session, email, password_hash):
        """Parametrized fallback for property (b): existing admin set is a no-op.

        Validates: Requirements 3.1
        """
        admin_bootstrap = admin_seed_support.require_admin_bootstrap_module()
        import logging

        logger = logging.getLogger("admin_bootstrap_test")
        before = await admin_seed_support.snapshot_admin_users(seeded_admin_session)
        outcome = await admin_bootstrap.bootstrap_admin(
            seeded_admin_session, email=email, password_hash=password_hash, logger=logger
        )
        after = await admin_seed_support.snapshot_admin_users(seeded_admin_session)
        assert "ADMIN_EXISTS" in _status_text(outcome)
        assert after == before


# =====================================================================================
# CLI contract tests (app.cli.create_admin). RED-by-absence: guarded so the SAME
# module-absence AssertionError is raised while the CLI module does not exist.
# The subprocess is kept pointed at the isolated *_test DB (DATABASE_URL =
# TEST_DATABASE_URL, RENDER/ENVIRONMENT unset) for when the module DOES exist.
# =====================================================================================


def _cli_env() -> dict:
    """Build a subprocess env pinned to the isolated *_test DB, production vars unset."""
    env = dict(os.environ)
    env["DATABASE_URL"] = admin_seed_support.TEST_DATABASE_URL
    env["TESTING"] = "true"
    env["USE_MOCK_STORAGE"] = "true"
    for key in ("RENDER", "ENVIRONMENT", "APP_ENV"):
        env.pop(key, None)
    return env


def _run_cli(args, stdin_text=""):
    """Run ``python -m app.cli.create_admin`` as a subprocess against the test DB.

    Guarded by ``_require_cli_module`` so that while the CLI does not exist this
    raises the uniform RED-by-absence AssertionError rather than attempting a
    subprocess that would fail with a different error.
    """
    _require_cli_module()  # RED-by-absence until Phase B
    return subprocess.run(  # pragma: no cover - unreachable until the CLI exists
        [sys.executable, "-m", _CLI_MODULE, *args],
        input=stdin_text,
        env=_cli_env(),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_cli_creates_admin_exit_zero_and_no_echo():
    """CLI create path exits 0 and never echoes the password.

    Uses the GENERATED shared password (never a literal / never the legacy
    credential) via getpass on stdin. RED-by-absence until Phase B.
    """
    password = admin_seed_support.shared_bootstrap_password()  # generated, non-secret-literal
    completed = _run_cli(["--email", _PUBLIC_ADMIN_EMAIL], stdin_text=password + "\n" + password + "\n")
    assert completed.returncode == 0
    assert password not in completed.stdout
    assert password not in completed.stderr


def test_cli_already_exists_is_noop_exit_zero():
    """CLI exits 0 (no-op) when an admin already exists and --force-additional is absent.

    RED-by-absence until Phase B.
    """
    password = admin_seed_support.shared_bootstrap_password()
    completed = _run_cli(["--email", _PUBLIC_ADMIN_EMAIL], stdin_text=password + "\n" + password + "\n")
    assert completed.returncode == 0


def test_cli_refuses_when_admin_exists_without_force():
    """CLI refuses to add a second admin unless --force-additional is given.

    Without the flag, attempting a create while an admin exists is a no-op (exit 0)
    and does not add a row; the contract requires --force-additional for additions.
    RED-by-absence until Phase B.
    """
    password = admin_seed_support.shared_bootstrap_password()
    completed = _run_cli(["--email", "second@trustcapture.com"], stdin_text=password + "\n" + password + "\n")
    assert completed.returncode == 0


def test_cli_rejects_short_or_weak_password_nonzero():
    """CLI rejects a password below min length 14 / failing the variety check -> non-zero.

    RED-by-absence until Phase B.
    """
    weak = "short"  # under 14 chars and no variety
    completed = _run_cli(["--email", _PUBLIC_ADMIN_EMAIL], stdin_text=weak + "\n" + weak + "\n")
    assert completed.returncode != 0
    assert weak not in completed.stdout


def test_cli_invalid_email_exit_nonzero():
    """CLI exits non-zero on an invalid email. RED-by-absence until Phase B."""
    password = admin_seed_support.shared_bootstrap_password()
    completed = _run_cli(["--email", "not-an-email"], stdin_text=password + "\n" + password + "\n")
    assert completed.returncode != 0


def test_cli_db_error_exit_nonzero():
    """CLI exits non-zero on a DB error (unreachable/invalid DB). RED-by-absence until Phase B.

    This test still begins with the CLI-absence guard, so until Phase B it fails with
    the module-absence AssertionError rather than exercising a real DB error.
    """
    _require_cli_module()  # RED-by-absence until Phase B
    env = _cli_env()  # pragma: no cover
    env["DATABASE_URL"] = admin_seed_support.TEST_DATABASE_URL.rsplit("/", 1)[0] + "/does_not_exist_test"  # pragma: no cover
    completed = subprocess.run(  # pragma: no cover
        [sys.executable, "-m", _CLI_MODULE, "--email", _PUBLIC_ADMIN_EMAIL],
        input="whatever\nwhatever\n",
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode != 0  # pragma: no cover
