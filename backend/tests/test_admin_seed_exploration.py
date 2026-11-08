"""Phase A bug-condition EXPLORATION test for the admin-seed-credential-fix spec.

Spec: .kiro/specs/admin-seed-credential-fix (Task 5.2.1, Property 1).

EXPECTED TO FAIL ON THE UNFIXED BASE. The RED is the success signal: it confirms
the Property 1 bug condition. Do NOT "fix" the code or weaken the assertion to make
this pass. The orchestrator classifies the failure; Phase B later makes it green.

Property 1 (Bug Condition)
--------------------------
``isBugCondition`` holds when ``admin_users`` is EMPTY and the current ``start.sh``
seed step creates an admin from a source literal. Under the FIX, running the seed
against an empty table must create ZERO admins (it should instead log
``NO_ADMIN_NO_BOOTSTRAP`` and create nothing). On the UNFIXED base the inline
heredoc creates exactly one admin from the legacy seed credential, so the
``count == 0`` assertion fails -> bug confirmed.

Validates: Requirements 1.2, 2.3

How it runs (tracks REAL behavior; no reimplementation)
-------------------------------------------------------
  * The admin seed python block is extracted PROGRAMMATICALLY from ``backend/start.sh``
    by slicing the lines between the ``SEEDEOF`` heredoc markers. We execute THAT
    exact block, so the test tracks what production actually runs.
  * The block is run in a subprocess with ``cwd`` = the backend directory (so
    ``from app...`` imports resolve) and an environment where ``DATABASE_URL`` is
    overridden to the validated, isolated ``*_test`` database and ``RENDER`` /
    ``ENVIRONMENT`` / ``APP_ENV`` are UNSET (so no production-looking env).
  * The ``admin_users`` table exists because the shared session-scoped
    ``setup_test_database`` fixture (conftest) creates the schema. This test depends
    on that fixture and additionally asserts isolation via ``assert_isolated_db``.

Secret hygiene
--------------
Never prints or records the legacy seed credential, its hash value, or any DB URL /
password. On failure the counterexample records ONLY: the admin count, the admin
email (``admin@trustcapture.com`` is already public and non-secret), and the LENGTH
of the stored ``password_hash`` (never its value).
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

# Importing admin_seed_support imports hotfix_support first, whose import-time
# fail-closed validator aborts collection unless the real env points at an isolated
# loopback ``*_test`` PostgreSQL database. So this module only collects when safe.
from tests import admin_seed_support

# --- Locate start.sh relative to this test file (worktree-independent) -----------
# tests/ -> backend/ -> backend/start.sh
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_START_SH = _BACKEND_DIR / "start.sh"

_SEED_HEREDOC_MARKER = "SEEDEOF"


def _extract_admin_seed_block() -> str:
    """Return the admin seed python block sliced from start.sh between SEEDEOF markers.

    Finds the line that opens the heredoc (``python3 << 'SEEDEOF'``) and the line
    that closes it (a line equal to ``SEEDEOF``), returning everything strictly
    between them. Raises AssertionError (a HARNESS error, not bug evidence) if the
    markers cannot be located, so a structural change in start.sh is loud.
    """
    assert _START_SH.is_file(), f"harness: start.sh not found at {_START_SH}"
    lines = _START_SH.read_text().splitlines()

    open_idx = None
    close_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if open_idx is None:
            # e.g. python3 << 'SEEDEOF'
            if stripped.startswith("python3 <<") and _SEED_HEREDOC_MARKER in stripped:
                open_idx = i
            continue
        if stripped == _SEED_HEREDOC_MARKER:
            close_idx = i
            break

    assert open_idx is not None, (
        f"harness: could not find opening '{_SEED_HEREDOC_MARKER}' heredoc in start.sh"
    )
    assert close_idx is not None and close_idx > open_idx, (
        f"harness: could not find closing '{_SEED_HEREDOC_MARKER}' marker in start.sh"
    )

    block = "\n".join(lines[open_idx + 1:close_idx])
    assert "AdminUser" in block and "AsyncSessionLocal" in block, (
        "harness: extracted block does not look like the admin seed step"
    )
    return block


def _subprocess_env() -> dict:
    """Build the subprocess env: test DB as DATABASE_URL, production vars unset.

    ``app.core.database`` binds its engine/``AsyncSessionLocal`` from ``DATABASE_URL``
    at import, so overriding it points the extracted seed block at the isolated
    ``*_test`` database. The validated ``TEST_DATABASE_URL`` already uses the asyncpg
    driver, so it is suitable as-is. Production-looking vars are removed.
    """
    env = dict(os.environ)
    # Point the real seed block at the isolated test database only.
    env["DATABASE_URL"] = admin_seed_support.TEST_DATABASE_URL
    env["TESTING"] = "true"
    env["USE_MOCK_STORAGE"] = "true"
    for key in ("RENDER", "ENVIRONMENT", "APP_ENV"):
        env.pop(key, None)
    return env


async def _delete_all_admins(session) -> None:
    await session.execute(text("DELETE FROM admin_users"))
    await session.commit()


async def _count_admins(session) -> int:
    result = await session.execute(text("SELECT COUNT(*) FROM admin_users"))
    return int(result.scalar_one())


async def _seeded_admin_fingerprint(session):
    """Return a secret-free fingerprint of seeded rows for the counterexample.

    Returns a list of (email, password_hash_length) tuples. The password hash VALUE
    is never read into the message - only its length - and the email is the already
    public, non-secret platform admin address.
    """
    result = await session.execute(
        text("SELECT email, LENGTH(password_hash) AS hlen FROM admin_users ORDER BY email")
    )
    return [(row.email, int(row.hlen)) for row in result]


@pytest.mark.asyncio
async def test_empty_table_seed_creates_no_known_password_admin(setup_test_database):
    """Property 1 RED: current start.sh seed on an EMPTY table must create ZERO admins.

    EXPECTED to FAIL on the unfixed base (the inline heredoc seeds exactly one
    admin from the legacy seed credential). The failure IS the confirmation of the
    bug condition. ``setup_test_database`` (session fixture, conftest) guarantees the
    ``admin_users`` table exists.
    """
    sessions, engine = admin_seed_support.make_test_sessionmaker()
    try:
        # Isolation guard + arrange: start from a provably isolated, EMPTY table.
        async with sessions() as session:
            await admin_seed_support.assert_isolated_db(session)
            await _delete_all_admins(session)
            assert await _count_admins(session) == 0, (
                "harness: admin_users was not empty after cleanup before the seed run"
            )

        # Act: run the REAL extracted start.sh admin seed block against the test DB.
        seed_block = _extract_admin_seed_block()
        completed = subprocess.run(
            [sys.executable, "-"],
            input=seed_block,
            env=_subprocess_env(),
            cwd=str(_BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )

        # A non-zero exit here most likely means the block could not import/connect:
        # that is a HARNESS failure, not genuine bug evidence. Surface it loudly.
        assert completed.returncode == 0, (
            "harness: seed subprocess exited non-zero (import/connection problem, "
            "not bug evidence).\n"
            f"returncode={completed.returncode}\n"
            f"stdout={completed.stdout}\n"
            f"stderr={completed.stderr}"
        )

        # Assert (expectation under the FIX): the empty table stays empty.
        async with sessions() as session:
            count = await _count_admins(session)
            if count != 0:
                fingerprint = await _seeded_admin_fingerprint(session)
                # Secret-free counterexample: count, public email, hash LENGTH only.
                pytest.fail(
                    "Property 1 bug condition CONFIRMED (expected RED on unfixed base): "
                    "running the current start.sh admin seed against an EMPTY admin_users "
                    f"created {count} admin row(s); expected 0 under the fix. "
                    f"counterexample (no secret values) = {fingerprint} "
                    "(tuples are (email, password_hash_length); the hash VALUE is never "
                    "recorded)."
                )
            assert count == 0
    finally:
        # Clean up so no seeded row leaks into other tests, then dispose the engine.
        try:
            async with sessions() as session:
                await _delete_all_admins(session)
        finally:
            await engine.dispose()


# =====================================================================================
# Task 5.2.2 - Property 1 (Bug Condition): structural repo guard for a hardcoded
# admin password. Appended alongside 5.2.1 (section 5.2 = this module). The existing
# 5.2.1 test above is unchanged.
#
# EXPECTED TO FAIL ON THE UNFIXED BASE; the failure lists the files still carrying a
# hardcoded admin password. No secret value is read from a committed source into this
# file, and no secret value is ever written to this file or emitted in any message:
# the guard reports ONLY file paths and line numbers.
#
# Validates: Requirements 1.1, 1.3, 2.1, 2.5
#
# What it checks (purely STRUCTURAL)
# ----------------------------------
#   * Enumerate TRACKED files via ``git ls-files`` from the repo root, filtered to
#     ``*.py`` plus ``backend/start.sh``.
#   * Python files are parsed with ``ast``. A file+line is FLAGGED when:
#       - a ``hash_password(...)`` call (callee is ``ast.Name`` ``hash_password`` or
#         ``ast.Attribute`` with ``.attr == "hash_password"``) receives a NON-EMPTY
#         ``str`` ``ast.Constant`` as its first positional password argument; OR
#       - an ``AdminUser(...)`` call has a keyword ``password_hash`` whose value is a
#         NON-EMPTY ``str`` ``ast.Constant``; OR
#       - a bare ``str`` ``ast.Constant`` equals the legacy seed credential. That
#         credential value is derived at RUNTIME, in memory only, from the
#         ``hash_password`` call already present in the committed ``conftest.py`` and
#         is NEVER written to this file and NEVER emitted. This broad check catches
#         the literal where it is used outside a ``hash_password``/``AdminUser`` call.
#   * ``start.sh`` is not importable, so it is scanned as text with a regex that
#     matches ``hash_password("...")`` / ``hash_password('...')`` with a non-empty
#     literal and records ONLY the file name and 1-based line number. The captured
#     literal is discarded; it never appears in any message.
#
# Expectation under the FIX: the flagged list is EMPTY. On the unfixed base it lists
# ``start.sh`` and the four test files, so this test FAILS -> bug confirmed.
# =====================================================================================
import ast as _ast
import re as _re

# tests/ -> backend/ -> repo root (worktree-independent).
_REPO_ROOT = _BACKEND_DIR.parent
_START_SH_FOR_GUARD = _BACKEND_DIR / "start.sh"

# Regex for start.sh: hash_password( "..." ) or hash_password( '...' ) with a
# NON-EMPTY literal. The literal is captured only to test non-emptiness; its text is
# never placed in any message.
_SH_HASH_PASSWORD_RE = _re.compile(r"""hash_password\(\s*(['"])(.+?)\1\s*\)""")


def _password_arg_is_nonempty_str_literal(node: _ast.AST) -> bool:
    return isinstance(node, _ast.Constant) and isinstance(node.value, str) and node.value != ""


def _callee_name(call: _ast.Call):
    func = call.func
    if isinstance(func, _ast.Name):
        return func.id
    if isinstance(func, _ast.Attribute):
        return func.attr
    return None


def _legacy_seed_literal():
    """Derive the legacy ADMIN seed credential in memory from ``start.sh``.

    ``start.sh`` is the authoritative admin-seed site: by the definition of this
    bug, the literal it passes to ``hash_password(...)`` IS the legacy seed
    credential. Deriving from here (rather than from a test file, which may also
    hold unrelated non-admin test passwords) pins the guard to exactly that value,
    so the broad arm flags the admin credential wherever it is reused and never
    false-flags other test users' passwords.

    Returns the literal string (used ONLY to locate equal literals elsewhere; never
    written to this file and never emitted in any message) or ``None`` if
    ``start.sh`` no longer embeds one. Returning ``None`` disables the broad arm,
    e.g. after the Phase B fix removes the literal from ``start.sh``.
    """
    if not _START_SH_FOR_GUARD.is_file():
        return None
    for match in _SH_HASH_PASSWORD_RE.finditer(_START_SH_FOR_GUARD.read_text()):
        captured = match.group(2)  # used ONLY as the comparison key; never emitted
        if captured != "":
            return captured
    return None


def _git_tracked_guard_files():
    """Return tracked guard targets: every ``*.py`` plus ``backend/start.sh``.

    Enumerated via ``git ls-files`` run from the repo root of this worktree. Raises
    AssertionError (a HARNESS error, not bug evidence) if git enumeration fails, so a
    broken enumeration is never silently treated as a clean repo.
    """
    try:
        completed = subprocess.run(
            ["git", "ls-files"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - harness
        raise AssertionError(f"harness: git ls-files could not run: {type(exc).__name__}")
    assert completed.returncode == 0, (
        "harness: git ls-files exited non-zero (enumeration problem, not bug "
        f"evidence).\nreturncode={completed.returncode}\nstderr={completed.stderr}"
    )
    tracked = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    py_files = [rel for rel in tracked if rel.endswith(".py")]
    start_sh = [rel for rel in tracked if rel == "backend/start.sh"]
    assert start_sh, "harness: backend/start.sh is not tracked by git in this worktree"
    assert py_files, "harness: git ls-files returned no Python files (enumeration problem)"
    return py_files, start_sh[0]


def _scan_python_file(rel_path: str, legacy_literal):
    """Return a list of 1-based line numbers in ``rel_path`` that carry a hardcoded
    admin password, using the structural rules documented above. Values are never
    returned - only line numbers.
    """
    abs_path = _REPO_ROOT / rel_path
    try:
        source = abs_path.read_text()
    except (OSError, UnicodeDecodeError):  # pragma: no cover - harness
        return []
    try:
        tree = _ast.parse(source, filename=rel_path)
    except SyntaxError as exc:  # pragma: no cover - harness
        raise AssertionError(
            f"harness: could not parse tracked Python file {rel_path}: "
            f"{type(exc).__name__} at line {exc.lineno}"
        )

    lines = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Call):
            name = _callee_name(node)
            # Arm 1: hash_password(<str literal>) where the literal IS the legacy
            # admin credential. Gating on equality keeps the guard scoped to the
            # admin seed credential and avoids flagging unrelated test-user passwords.
            if (
                name == "hash_password"
                and node.args
                and _password_arg_is_nonempty_str_literal(node.args[0])
                and legacy_literal is not None
                and node.args[0].value == legacy_literal
            ):
                lines.add(node.args[0].lineno)
            # Arm 2: AdminUser(..., password_hash=<non-empty str literal>). Any admin
            # constructed with a string-literal password hash is in scope regardless
            # of value, so this arm is unconditional.
            if name == "AdminUser":
                for kw in node.keywords:
                    if kw.arg == "password_hash" and _password_arg_is_nonempty_str_literal(kw.value):
                        lines.add(kw.value.lineno)
        # Arm 3: any bare str constant equal to the legacy admin seed credential.
        if (
            legacy_literal is not None
            and isinstance(node, _ast.Constant)
            and isinstance(node.value, str)
            and node.value == legacy_literal
        ):
            lines.add(node.lineno)
    return sorted(lines)


def _scan_start_sh(rel_path: str):
    """Return 1-based line numbers in start.sh where ``hash_password("...")`` passes a
    non-empty literal. Only line numbers are returned; the captured literal is dropped.
    """
    abs_path = _REPO_ROOT / rel_path
    lines = []
    for lineno, line in enumerate(abs_path.read_text().splitlines(), start=1):
        for match in _SH_HASH_PASSWORD_RE.finditer(line):
            captured = match.group(2)  # used ONLY for the non-empty test; never emitted
            if captured != "":
                lines.append(lineno)
                break
    return lines


def test_no_tracked_file_contains_a_hardcoded_admin_password():
    """Property 1 RED guard: no tracked file may hardcode an admin password.

    EXPECTED to FAIL on the unfixed base: ``start.sh`` and the four test files still
    carry the legacy seed credential. The failure message lists ONLY file paths and
    line numbers - never the password value. Under the Phase B fix the flagged list
    is empty and this test turns green.
    """
    legacy_literal = _legacy_seed_literal()
    py_files, start_sh_rel = _git_tracked_guard_files()

    flagged = []  # list of (file_path, line_number) - NEVER any value
    for rel in py_files:
        for lineno in _scan_python_file(rel, legacy_literal):
            flagged.append((rel, lineno))
    for lineno in _scan_start_sh(start_sh_rel):
        flagged.append((start_sh_rel, lineno))

    flagged.sort()
    if flagged:
        rendered = "\n".join(f"  {path}:{line}" for path, line in flagged)
        flagged_files = sorted({path for path, _ in flagged})
        pytest.fail(
            "Property 1 bug condition CONFIRMED (expected RED on unfixed base): "
            f"{len(flagged)} hardcoded admin-password site(s) across "
            f"{len(flagged_files)} tracked file(s). Locations (file:line only, no "
            "secret value is read or embedded):\n" + rendered
        )
    assert flagged == []