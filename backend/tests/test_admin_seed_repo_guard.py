"""Phase A structural repo-guard test for the admin-seed-credential-fix spec.

Spec: .kiro/specs/admin-seed-credential-fix (Task 5.2.2, Property 1 - Bug Condition).

EXPECTED TO FAIL ON THE UNFIXED BASE. The RED is the success signal: it confirms
that tracked files still construct an admin (or hash a password) from a string
LITERAL. Do NOT "fix" the code or weaken the assertion to make this pass; Phase B
later removes the literals and this turns green.

Property 1 (Bug Condition)
--------------------------
No code path may create an admin with a known/hardcoded password, and no tracked
file may construct a password hash (or an ``AdminUser``) from a string literal. The
bootstrap secret must come only from outside the repo.

Validates: Requirements 1.1, 1.3, 2.1, 2.5

Design: VALUE-AGNOSTIC, pattern-only
------------------------------------
This guard detects the structural PATTERN of a hardcoded password; it NEVER reads,
derives, embeds, or emits the legacy seed credential, its hash, or any digest of it.
The whole point is that it keeps working after the value is rotated and without the
value ever touching this file, logs, or test output.

Tracked files are enumerated via ``git ls-files`` from the repo root of THIS
worktree, filtered to ``*.py`` plus ``backend/start.sh``. A file + line is FLAGGED
by one of three structural arms:

  Arm 1 - Python ``hash_password(<non-empty str literal>)``: a call whose callee is
          named ``hash_password`` (``ast.Name.id`` or ``ast.Attribute.attr``) and
          whose FIRST positional argument is a non-empty ``str`` ``ast.Constant``.
  Arm 2 - Python ``AdminUser(..., password_hash=<non-empty str literal>)``: a call
          whose callee is named ``AdminUser`` with a keyword argument
          ``password_hash`` whose value is a non-empty ``str`` ``ast.Constant``.
          (The common nested form ``AdminUser(password_hash=hash_password("..."))``
          is already covered by Arm 1 via the inner ``hash_password`` literal.)
  Arm 3 - ``backend/start.sh`` (a heredoc, not importable) scanned as text with a
          regex matching ``hash_password("...")`` / ``hash_password('...')`` holding
          a non-empty literal.

Each arm records ONLY ``(file_path, line_number)``. The literal captured by the
regex in Arm 3 is used solely to test non-emptiness and is then discarded; no
``ast.Constant`` value is ever placed in a message. The guard asserts ZERO hits.

Self-exclusion
--------------
The new Phase A test files and ``admin_seed_support.py`` are not flagged: they do
not pass a string LITERAL to ``hash_password``/``AdminUser``.
``admin_seed_support`` calls ``hash_password(shared_bootstrap_password())`` - a
call argument, not a ``str`` constant - so Arm 1 does not trigger. This test file
and ``test_admin_seed_exploration.py`` reference ``hash_password`` only inside
regex/strings/comments, never as a call with a literal argument.
"""
import ast
import re
import subprocess
from pathlib import Path

import pytest

# tests/ -> backend/ -> repo root (worktree-independent).
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent
_START_SH_REL = "backend/start.sh"

# Arm 3 regex: hash_password( "..." ) or hash_password( '...' ) with a NON-EMPTY
# literal. The captured group is used ONLY to test non-emptiness; its text is never
# placed in any message.
_SH_HASH_PASSWORD_RE = re.compile(r"""hash_password\(\s*(['"])(.+?)\1""")


def _is_nonempty_str_constant(node: ast.AST) -> bool:
    """True iff ``node`` is a non-empty ``str`` constant (value-agnostic)."""
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value != ""
    )


def _callee_name(call: ast.Call):
    """Return the simple callee name of a Call (``Name.id`` or ``Attribute.attr``)."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _git_tracked_guard_files():
    """Return ``(python_files, start_sh_rel)`` of tracked guard targets.

    Enumerated via ``git ls-files`` run with ``cwd`` at the repo root of THIS
    worktree, so it lists this worktree's tracked set. Raises ``AssertionError`` (a
    HARNESS error, NOT bug evidence) if enumeration fails, so a broken enumeration is
    never silently mistaken for a clean repo.
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
        raise AssertionError(
            f"harness: git ls-files could not run: {type(exc).__name__}"
        )
    assert completed.returncode == 0, (
        "harness: git ls-files exited non-zero (enumeration problem, not bug "
        f"evidence).\nreturncode={completed.returncode}\nstderr={completed.stderr}"
    )
    tracked = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    py_files = [rel for rel in tracked if rel.endswith(".py")]
    start_sh = [rel for rel in tracked if rel == _START_SH_REL]
    assert start_sh, (
        "harness: backend/start.sh is not tracked by git in this worktree"
    )
    assert py_files, (
        "harness: git ls-files returned no Python files (enumeration problem)"
    )
    return py_files, start_sh[0]


def _scan_python_file(rel_path: str):
    """Return sorted 1-based line numbers in ``rel_path`` flagged by Arm 1 or Arm 2.

    Only line numbers are returned - never any value. A file that cannot be read is
    skipped (recorded as no hits). A file that fails to parse raises ``AssertionError``
    (a HARNESS error) so a broken enumeration is loud rather than a false clean.
    """
    abs_path = _REPO_ROOT / rel_path
    try:
        source = abs_path.read_text()
    except (OSError, UnicodeDecodeError):  # pragma: no cover - harness
        return []
    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as exc:  # pragma: no cover - harness
        raise AssertionError(
            f"harness: could not parse tracked Python file {rel_path}: "
            f"{type(exc).__name__} at line {exc.lineno}"
        )

    lines = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _callee_name(node)
        # Arm 1: hash_password(<non-empty str literal>) as the first positional arg.
        if name == "hash_password" and node.args and _is_nonempty_str_constant(node.args[0]):
            lines.add(node.args[0].lineno)
        # Arm 2: AdminUser(..., password_hash=<non-empty str literal>).
        if name == "AdminUser":
            for kw in node.keywords:
                if kw.arg == "password_hash" and _is_nonempty_str_constant(kw.value):
                    lines.add(kw.value.lineno)
    return sorted(lines)


def _scan_start_sh(rel_path: str):
    """Return sorted 1-based line numbers in start.sh flagged by Arm 3.

    Matches ``hash_password("...")`` with a non-empty literal. Only line numbers are
    returned; the captured literal is dropped and never emitted.
    """
    abs_path = _REPO_ROOT / rel_path
    assert abs_path.is_file(), f"harness: {rel_path} not found at {abs_path}"
    lines = []
    for lineno, line in enumerate(abs_path.read_text().splitlines(), start=1):
        for match in _SH_HASH_PASSWORD_RE.finditer(line):
            captured = match.group(2)  # used ONLY for the non-empty test; never emitted
            if captured != "":
                lines.append(lineno)
                break
    return lines


def test_no_tracked_file_constructs_admin_password_from_a_literal():
    """Property 1 RED guard: no tracked file may build a password hash / admin from a literal.

    EXPECTED to FAIL on the unfixed base: ``backend/start.sh`` and
    ``backend/tests/conftest.py`` still pass string literals to
    ``hash_password(...)`` / ``AdminUser(...)``. The failure message lists ONLY file
    paths and line numbers - never the password value. Under the Phase B fix the
    flagged list is empty and this test turns green.
    """
    py_files, start_sh_rel = _git_tracked_guard_files()

    flagged = []  # list of (file_path, line_number) - NEVER any value
    for rel in py_files:
        for lineno in _scan_python_file(rel):
            flagged.append((rel, lineno))
    for lineno in _scan_start_sh(start_sh_rel):
        flagged.append((start_sh_rel, lineno))

    flagged.sort()
    if flagged:
        rendered = "\n".join(f"  {path}:{line}" for path, line in flagged)
        flagged_files = sorted({path for path, _ in flagged})
        pytest.fail(
            "Property 1 bug condition CONFIRMED (expected RED on unfixed base): "
            f"{len(flagged)} string-literal admin-password site(s) across "
            f"{len(flagged_files)} tracked file(s). Flagged files: "
            f"{flagged_files}. Locations (file:line only; no secret value is read, "
            "derived, or embedded):\n" + rendered
        )
    assert flagged == []
