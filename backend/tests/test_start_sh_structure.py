"""Phase B start.sh structure test (task 5.6) for admin-seed-credential-fix.

Purpose
-------
Pin the SHAPE that the Phase B fix will give ``backend/start.sh`` and prove that
shape is ABSENT on the unfixed base. This is a tests-first (RED) artifact:

  * ``test_start_sh_invokes_bootstrap_module``  -> FAILS today (RED by absence):
    the fix will make start.sh call ``python -m app.core.admin_bootstrap`` instead
    of inlining the admin seed. That invocation does not exist yet. (PRIMARY RED.)

  * ``test_start_sh_has_no_inline_literal_password`` -> FAILS today (RED): the
    current start.sh still builds an admin password from an inline string literal
    (``hash_password("...")``). The fix removes it. Reports file + line number
    ONLY, never the literal value.

  * ``test_tenant_seed_block_identical_to_origin_main`` -> PASSES today and must
    keep passing after Phase B: the default-tenant seed heredoc (between
    ``TENANTEOF`` markers) must stay byte-for-byte identical to
    ``origin/main:backend/start.sh``. Mirrors the task 5.5 comparison so the
    structure test also pins the tenant block.

Net pytest outcome on the unfixed base: 2 failed, 1 passed (GENUINE-RED: the
structure the fix introduces is simply not there yet; these are real assert
failures, not harness errors). After Phase B all three go green.

Reads start.sh as text only -- no database is used by any assertion here. The
module still imports ``admin_seed_support`` (which imports ``hotfix_support``
first) so collection stays inside the fail-closed safety layer like its siblings.

Secret hygiene
--------------
Never writes or prints the legacy seed credential, its hash, any digest of it, or
any DB URL / password. The inline-literal check reports only the file path and
1-based line number of the offending ``hash_password(`` call -- never the matched
text or the quoted value.
"""
import re
import subprocess
from pathlib import Path

# Importing admin_seed_support imports hotfix_support first, whose import-time
# fail-closed validator aborts collection unless the real env points at an
# isolated loopback ``*_test`` PostgreSQL database. So this module only collects
# when safe, consistent with the other Phase A test modules.
from tests import admin_seed_support  # noqa: F401  (import-time safety guard)

# --- Locate paths relative to this test file (worktree-independent) --------------
# tests/ -> backend/ -> backend/start.sh ; backend/ -> repo root
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent
_START_SH = _BACKEND_DIR / "start.sh"

_TENANT_HEREDOC_MARKER = "TENANTEOF"

# The fixed start.sh must invoke the bootstrap module. Accept either ``python`` or
# ``python3`` as the interpreter, with flexible intervening whitespace.
_BOOTSTRAP_INVOCATION_RE = re.compile(r"python3?\s+-m\s+app\.core\.admin_bootstrap")

# An inline string-literal password construction, e.g. hash_password("....") or
# hash_password('....'). The regex matches ``hash_password(`` immediately followed
# (after optional whitespace) by an opening quote. We deliberately capture ONLY up
# to the opening quote so the literal value is never materialised or reported.
_INLINE_HASH_LITERAL_RE = re.compile(r"""hash_password\(\s*["']""")


def _read_start_sh_lines() -> list:
    """Return start.sh as a list of lines, or raise a HARNESS AssertionError."""
    assert _START_SH.is_file(), f"harness: start.sh not found at {_START_SH}"
    return _START_SH.read_text().splitlines()


def _extract_heredoc_block(marker: str) -> str:
    """Return the python block sliced from start.sh between ``marker`` heredocs.

    Finds the line opening the heredoc (``python3 << 'MARKER'``) and the line that
    is exactly ``MARKER``, returning everything strictly between them. Raises a
    HARNESS AssertionError (not a structure failure) if the markers cannot be
    located, so a structural change in start.sh is loud.
    """
    lines = _read_start_sh_lines()

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


# =============================================================================
# Structure assertion 1 (PRIMARY RED until Phase B): start.sh calls the module
# =============================================================================
def test_start_sh_invokes_bootstrap_module():
    """start.sh must invoke ``python -m app.core.admin_bootstrap``.

    GENUINE-RED on the unfixed base: the invocation is absent because the admin
    seed is still inlined. Phase B replaces the inline heredoc with the module
    call, turning this green. This assertion reads start.sh as text; no DB is used.
    """
    lines = _read_start_sh_lines()
    matches = [i + 1 for i, line in enumerate(lines)
               if _BOOTSTRAP_INVOCATION_RE.search(line)]

    assert matches, (
        "start.sh does not invoke the bootstrap module: expected a line matching "
        "'python -m app.core.admin_bootstrap' (python3 accepted) in "
        f"{_START_SH}. Found 0 occurrences. On the unfixed base this is EXPECTED "
        "to fail (RED by absence); Phase B introduces the invocation. "
        "(Requirement 2.1)"
    )


# =============================================================================
# Structure assertion 2 (RED until Phase B): no inline literal password
# =============================================================================
def test_start_sh_has_no_inline_literal_password():
    """start.sh must NOT construct an admin password from a string literal.

    Flags any ``hash_password("...")`` / ``hash_password('...')`` call. Reports the
    file path and 1-based line number(s) ONLY -- never the matched text or the
    quoted value -- preserving secret hygiene.

    GENUINE-RED on the unfixed base: the inline literal is still present. Phase B
    removes it (the module receives a pre-hashed bootstrap secret instead),
    turning this green.
    """
    lines = _read_start_sh_lines()
    hit_linenos = [i + 1 for i, line in enumerate(lines)
                   if _INLINE_HASH_LITERAL_RE.search(line)]

    # Report only paths + line numbers; never the literal value.
    location_hint = ", ".join(f"{_START_SH}:{n}" for n in hit_linenos)
    assert not hit_linenos, (
        "start.sh constructs an admin password from an inline string literal via "
        f"hash_password(<literal>) at: {location_hint}. The password must come "
        "from an out-of-band bootstrap secret, never a source literal. On the "
        "unfixed base this is EXPECTED to fail (RED); Phase B removes the inline "
        "literal. (value intentionally not shown) (Requirements 2.1, 3.4)"
    )


# =============================================================================
# Tenant-block pin (PASSES today and after Phase B): byte-for-byte vs origin/main
# =============================================================================
def test_tenant_seed_block_identical_to_origin_main():
    """The tenant heredoc must be byte-for-byte unchanged vs origin/main.

    Extracts the tenant block (between ``TENANTEOF`` markers) from the worktree
    ``backend/start.sh`` and compares it byte-for-byte with the same block from
    ``git show origin/main:backend/start.sh``. Identical today (no change yet) and
    must stay identical after Phase B. Mirrors task 5.5 so the structure test also
    pins the tenant block.
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
        f"(enumeration problem, not a structure failure).\n"
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
