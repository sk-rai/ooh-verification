"""Phase A PRESERVATION test for the admin-seed-credential-fix spec.

Spec: .kiro/specs/admin-seed-credential-fix (Task 5.5, Property 2).

EXPECTED OUTCOME: PASS now (on the unfixed base) AND it MUST still pass after the
Phase B fix. This is the observation-first preservation contract: it observes the
CURRENT behavior and asserts the invariants that must hold ACROSS the fix. It has
NO dependency on the not-yet-built ``admin_bootstrap`` module (it never imports it),
so it is green today and stays green after Phase B.

Property 2 (Preservation)
-------------------------
For any deploy state where ``admin_users`` is NON-empty (the bug condition does NOT
hold), the seed step SHALL leave every existing row byte/field-identical, print
"Admin user exists", and the tenant seed block and the P0 auth tests SHALL be
unchanged.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5

What is asserted
----------------
  1. Existing-admin preservation under the CURRENT start.sh seed block: with one or
     two EXISTING admin rows present (inserted with a freshly GENERATED password
     hash from ``admin_seed_support`` -- never the legacy seed credential), running
     the REAL extracted seed block (sliced between the ``SEEDEOF`` markers) in a
     subprocess pointed at the isolated ``*_test`` database prints "Admin user
     exists", writes nothing, and leaves the full-row snapshot (all columns incl.
     ``password_hash``, ``is_active``, timestamps) and the row count identical.
  2. Tenant seed block immutability: the tenant heredoc (between ``TENANTEOF``
     markers) in the worktree ``backend/start.sh`` is byte-for-byte identical to the
     same block in ``git show origin/main:backend/start.sh``.
  3. P0 hotfix tests unchanged: the three P0 files are tracked and show no diff vs
     ``origin/main`` (``git diff --quiet`` exits 0). The P0 GREEN run itself is
     verified in task 6's full-suite run, not re-run here (no nested pytest).

Secret hygiene
--------------
Never writes or prints the legacy seed credential, its hash, any digest of it, or
any DB URL / password. Existing rows are inserted with the GENERATED shared hash
from ``admin_seed_support``. Any diagnostic message reports only non-secret facts
(row counts, column names, the already-public platform email, hash LENGTH).
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

# Importing admin_seed_support imports hotfix_support first, whose import-time
# fail-closed validator aborts collection unless the real env points at an isolated
# loopback ``*_test`` PostgreSQL database. So this module only collects when safe.
from tests import admin_seed_support

# --- Locate paths relative to this test file (worktree-independent) --------------
# tests/ -> backend/ -> backend/start.sh ; backend/ -> repo root
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent
_START_SH = _BACKEND_DIR / "start.sh"

_SEED_HEREDOC_MARKER = "SEEDEOF"
_TENANT_HEREDOC_MARKER = "TENANTEOF"

# The three P0 hotfix files that must stay unchanged vs origin/main.
_P0_FILES = (
    "backend/tests/test_admin_auth_hotfix_red.py",
    "backend/tests/test_admin_auth_hotfix_preservation.py",
    "backend/tests/test_admin_auth_coverage_guard.py",
)


def _extract_heredoc_block(marker: str) -> str:
    """Return the python block sliced from start.sh between ``marker`` heredocs.

    Finds the line that opens the heredoc (``python3 << 'MARKER'``) and the line
    that is exactly ``MARKER``, returning everything strictly between them. Raises
    AssertionError (a HARNESS error, not a preservation failure) if the markers
    cannot be located, so a structural change in start.sh is loud.
    """
    assert _START_SH.is_file(), f"harness: start.sh not found at {_START_SH}"
    lines = _START_SH.read_text().splitlines()

    open_idx = None
    close_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if open_idx is None:
            if stripped.startswith("python3 <<") and marker in stripped:
                open_idx = i
            continue
        if stripped == marker:
            close_idx = i
            break

    assert open_idx is not None, (
        f"harness: could not find opening '{marker}' heredoc in start.sh"
    )
    assert close_idx is not None and close_idx > open_idx, (
        f"harness: could not find closing '{marker}' marker in start.sh"
    )
    return "\n".join(lines[open_idx + 1:close_idx])


def _subprocess_env() -> dict:
    """Build the subprocess env: isolated test DB as DATABASE_URL, prod vars unset.

    ``app.core.database`` binds its engine / ``AsyncSessionLocal`` from
    ``DATABASE_URL`` at import, so overriding it points the extracted seed block at
    the isolated ``*_test`` database. ``RENDER`` / ``ENVIRONMENT`` / ``APP_ENV`` are
    removed so the environment never looks like production.
    """
    env = dict(os.environ)
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


def _make_existing_admin(email: str):
    """Build an AdminUser carrying the GENERATED shared hash (never the legacy value).

    Uses ``admin_seed_support.shared_bootstrap_password_hash()`` so no secret is
    embedded and the row is realistic (a real bcrypt hash from the app's hasher).
    """
    from app.models.admin_user import AdminUser

    return AdminUser(
        admin_id=uuid.uuid4(),
        email=email,
        password_hash=admin_seed_support.shared_bootstrap_password_hash(),
        name="Preservation Existing Admin",
        is_active=True,
    )


@pytest.mark.parametrize(
    "existing_emails",
    [
        # One existing row (the already-public platform email).
        ("admin@trustcapture.com",),
        # Two existing rows: an extra distinct admin plus the platform email.
        ("admin@trustcapture.com", "owner2@trustcapture.com"),
    ],
    ids=["one-existing-admin", "two-existing-admins"],
)
@pytest.mark.asyncio
async def test_existing_admins_preserved_by_current_seed(setup_test_database, existing_emails):
    """Property 2: existing admin rows are byte/field-identical across a seed run.

    Arrange one or two EXISTING admins (generated hash), snapshot every column, run
    the REAL start.sh admin seed block against the isolated test DB, and assert the
    seed no-ops: it prints "Admin user exists", the row count is unchanged, and the
    snapshot is identical field-for-field before and after. True on the unfixed base
    (the current block already no-ops when a row exists) and must remain true after
    Phase B.
    """
    sessions, engine = admin_seed_support.make_test_sessionmaker()
    try:
        # Arrange: provably isolated DB, start from an EXISTING (non-empty) state.
        async with sessions() as session:
            await admin_seed_support.assert_isolated_db(session)
            await _delete_all_admins(session)
            for email in existing_emails:
                session.add(_make_existing_admin(email))
            await session.commit()

        async with sessions() as session:
            before = await admin_seed_support.snapshot_admin_users(session)
        assert len(before) == len(existing_emails), (
            "harness: did not arrange the expected number of existing admins"
        )

        # Act: run the REAL extracted start.sh admin seed block against the test DB.
        seed_block = _extract_heredoc_block(_SEED_HEREDOC_MARKER)
        assert "AdminUser" in seed_block and "AsyncSessionLocal" in seed_block, (
            "harness: extracted block does not look like the admin seed step"
        )
        completed = subprocess.run(
            [sys.executable, "-"],
            input=seed_block,
            env=_subprocess_env(),
            cwd=str(_BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )

        # A non-zero exit means the block could not import/connect: HARNESS failure.
        assert completed.returncode == 0, (
            "harness: seed subprocess exited non-zero (import/connection problem, "
            "not a preservation failure).\n"
            f"returncode={completed.returncode}\n"
            f"stdout={completed.stdout}\n"
            f"stderr={completed.stderr}"
        )

        # Because an admin already exists, the seed must no-op and say so.
        assert "Admin user exists" in completed.stdout, (
            "expected the seed step to report 'Admin user exists' and write nothing "
            f"when an admin already exists; stdout did not contain it.\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
        assert "Admin user seeded" not in completed.stdout, (
            "the seed step must NOT create an admin when one already exists; stdout "
            f"reported seeding.\nstdout={completed.stdout}"
        )

        # Assert: nothing changed -- count and full-row snapshot are identical.
        async with sessions() as session:
            after_count = await _count_admins(session)
            after = await admin_seed_support.snapshot_admin_users(session)

        assert after_count == len(existing_emails), (
            f"row count changed: expected {len(existing_emails)}, got {after_count}"
        )
        assert after == before, (
            "existing admin row(s) were modified by the seed step; every column "
            "(incl. password_hash, is_active, timestamps) must be identical before "
            "and after. The hash VALUE is never emitted here."
        )
    finally:
        # Clean up so no row leaks into other tests, then dispose the engine.
        try:
            async with sessions() as session:
                await _delete_all_admins(session)
        finally:
            await engine.dispose()


def test_tenant_seed_block_identical_to_origin_main():
    """Property 2: the tenant heredoc block must be byte-for-byte unchanged.

    Extracts the tenant block (between ``TENANTEOF`` markers) from the worktree
    ``backend/start.sh`` and compares it byte-for-byte with the same block extracted
    from ``git show origin/main:backend/start.sh``. Guards Phase B from touching the
    tenant block. PASS today (no change yet) and must stay PASS after Phase B.
    """
    worktree_block = _extract_heredoc_block(_TENANT_HEREDOC_MARKER)

    completed = subprocess.run(
        ["git", "--no-pager", "show", "origin/main:backend/start.sh"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, (
        "harness: 'git show origin/main:backend/start.sh' exited non-zero "
        f"(enumeration problem, not a preservation failure).\n"
        f"returncode={completed.returncode}\nstderr={completed.stderr}"
    )

    origin_lines = completed.stdout.splitlines()
    open_idx = None
    close_idx = None
    for i, line in enumerate(origin_lines):
        stripped = line.strip()
        if open_idx is None:
            if stripped.startswith("python3 <<") and _TENANT_HEREDOC_MARKER in stripped:
                open_idx = i
            continue
        if stripped == _TENANT_HEREDOC_MARKER:
            close_idx = i
            break
    assert open_idx is not None and close_idx is not None and close_idx > open_idx, (
        "harness: could not locate the TENANTEOF block in origin/main:backend/start.sh"
    )
    origin_block = "\n".join(origin_lines[open_idx + 1:close_idx])

    assert worktree_block == origin_block, (
        "the default-tenant seed block in start.sh differs from origin/main; it must "
        "stay byte-for-byte unchanged (Property 2 / Requirement 3.3)."
    )


def test_p0_hotfix_files_unchanged_vs_origin_main():
    """Property 2: the three P0 hotfix test files are tracked and unmodified.

    Lightweight, non-nested check (no inner pytest run): assert each P0 file is
    tracked by git, then assert ``git diff --quiet origin/main -- <P0 files>`` exits
    0 (no modification). The P0 GREEN result itself is verified by the full-suite run
    in task 6. PASS today and must stay PASS after Phase B.
    """
    # Each P0 file is tracked by git.
    ls = subprocess.run(
        ["git", "--no-pager", "ls-files", "--", *_P0_FILES],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert ls.returncode == 0, (
        "harness: 'git ls-files' for the P0 files exited non-zero.\n"
        f"returncode={ls.returncode}\nstderr={ls.stderr}"
    )
    tracked = {line.strip() for line in ls.stdout.splitlines() if line.strip()}
    missing = [p for p in _P0_FILES if p not in tracked]
    assert not missing, f"P0 file(s) not tracked by git: {missing}"

    # No diff vs origin/main -> exit 0 means unchanged.
    diff = subprocess.run(
        ["git", "--no-pager", "diff", "--quiet", "origin/main", "--", *_P0_FILES],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert diff.returncode == 0, (
        "one or more P0 hotfix test files differ from origin/main; they must remain "
        f"unchanged (Property 2 / Requirement 3.5). Changed files among: {list(_P0_FILES)}"
    )