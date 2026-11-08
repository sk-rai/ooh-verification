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

# (SEEDEOF heredoc removed in Phase B -- start.sh now calls python -m app.core.admin_bootstrap)

@pytest.mark.asyncio
async def test_empty_table_seed_creates_no_known_password_admin(setup_test_database):
    """Property 1 (Phase B): the new start.sh admin step on an EMPTY table with no
    bootstrap env creates ZERO admins and emits NO_ADMIN_NO_BOOTSTRAP.

    This test previously ran the SEEDEOF heredoc (which seeded one known-password admin).
    Phase B removes that heredoc; the new step calls python -m app.core.admin_bootstrap,
    which on an empty table with no env creates nothing and logs a warning.

    EXPECTED: PASS (the fix is in place).
    """
    sessions, engine = admin_seed_support.make_test_sessionmaker()
    try:
        async with sessions() as session:
            await admin_seed_support.assert_isolated_db(session)
            await session.execute(text("DELETE FROM admin_users"))
            await session.commit()
            count_before = (await session.execute(text("SELECT COUNT(*) FROM admin_users"))).scalar()
            assert count_before == 0, "harness: admin_users not empty before test"

        env = dict(os.environ)
        env["DATABASE_URL"] = admin_seed_support.TEST_DATABASE_URL
        env["TESTING"] = "true"
        env["USE_MOCK_STORAGE"] = "true"
        for k in ("RENDER", "ENVIRONMENT", "APP_ENV",
                  "ADMIN_BOOTSTRAP_EMAIL", "ADMIN_BOOTSTRAP_PASSWORD_HASH"):
            env.pop(k, None)

        completed = subprocess.run(
            [sys.executable, "-m", "app.core.admin_bootstrap"],
            env=env,
            cwd=str(_BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=60,
        )
        combined = completed.stdout + completed.stderr
        assert completed.returncode == 0, (
            f"bootstrap module exited non-zero: {completed.returncode}\n"
            f"stdout: {completed.stdout[:300]}\nstderr: {completed.stderr[:300]}"
        )
        assert "NO_ADMIN_NO_BOOTSTRAP" in combined, (
            f"expected NO_ADMIN_NO_BOOTSTRAP in output; got:\n{combined[:500]}"
        )

        async with sessions() as session:
            count_after = (await session.execute(text("SELECT COUNT(*) FROM admin_users"))).scalar()
        assert count_after == 0, (
            f"FAIL: {count_after} admin(s) created on empty table with no bootstrap env; "
            f"expected 0. Combined output:\n{combined[:400]}"
        )
    finally:
        await engine.dispose()

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