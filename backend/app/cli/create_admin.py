"""Owner CLI to create a platform admin interactively.

Spec: .kiro/specs/admin-seed-credential-fix (Phase B, design.md Section B).

Usage::

    python -m app.cli.create_admin [--email admin@trustcapture.com] [--force-additional]

Behaviour:
  * Prompts for the password TWICE via ``getpass`` (hidden entry); the two must match.
  * Enforces min length 14 and a basic character-variety / entropy check.
  * Hashes with the app's own ``app.core.security.hash_password``.
  * Uses the SAME validator + insert path as the deploy bootstrap
    (``app.core.admin_bootstrap``) against a session built from ``DATABASE_URL``.
  * Refuses to create a second admin unless ``--force-additional`` is given; without
    the flag, when an admin already exists it is a no-op (exit 0).
  * NEVER echoes the password.

Exit codes:
  * 0  -> admin created, or existing-admin no-op (ADMIN_EXISTS / ALREADY_EXISTS).
  * 2  -> invalid input (weak/short/mismatched password, bad email, BOOTSTRAP_INVALID).
  * 3  -> database error (BOOTSTRAP_DB_ERROR) or unexpected failure.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import logging
import sys

from app.core.admin_bootstrap import (
    Status,
    bootstrap_admin,
    insert_admin_forced,
    normalize_email,
)
from app.core.security import hash_password

_DEFAULT_EMAIL = "admin@trustcapture.com"
_MIN_LEN = 14

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_DB_ERROR = 3


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("create_admin_cli")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def _password_variety_ok(password: str) -> bool:
    """Basic variety/entropy check: at least 3 of {lower, upper, digit, symbol}
    and not a single repeated character. Never logs the value.
    """
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(not c.isalnum() for c in password)
    classes = sum((has_lower, has_upper, has_digit, has_symbol))
    distinct = len(set(password))
    return classes >= 3 and distinct >= 8


def _prompt_password() -> str:
    """Prompt twice (hidden). Raises ValueError on mismatch / weak password.

    When ``ADMIN_CLI_STDIN_PASSWORD=1`` is set (test harness only) the prompts
    read from ``sys.stdin`` via ``input()`` so the subprocess can be driven via
    piped stdin without opening ``/dev/tty``. Never set this in production.
    """
    if os.environ.get("ADMIN_CLI_STDIN_PASSWORD") == "1":
        import sys as _sys
        print("New admin password: ", end="", flush=True)
        first = _sys.stdin.readline().rstrip("\n")
        print("Confirm admin password: ", end="", flush=True)
        second = _sys.stdin.readline().rstrip("\n")
    else:
        first = getpass.getpass("New admin password: ")
        second = getpass.getpass("Confirm admin password: ")
    if first != second:
        raise ValueError("passwords did not match")
    if len(first) < _MIN_LEN:
        raise ValueError(f"password too short (min {_MIN_LEN} characters)")
    if not _password_variety_ok(first):
        raise ValueError("password not varied enough (mix cases, digits, symbols)")
    return first


async def _admin_exists(session) -> bool:
    from sqlalchemy import text

    result = await session.execute(text("SELECT 1 FROM admin_users LIMIT 1"))
    return result.first() is not None


async def _run(email: str, force_additional: bool, password: str, log: logging.Logger) -> int:
    from app.core.database import AsyncSessionLocal

    normalized = normalize_email(email)
    if normalized is None:
        log.error("%s reason=bad_email", Status.BOOTSTRAP_INVALID)
        return EXIT_INVALID

    password_hash = hash_password(password)

    async with AsyncSessionLocal() as session:
        try:
            exists = await _admin_exists(session)
        except Exception as ex:  # noqa: BLE001
            log.error("%s exc=%s", Status.BOOTSTRAP_DB_ERROR, type(ex).__name__)
            return EXIT_DB_ERROR

        if exists and not force_additional:
            log.info("%s: an admin already exists; no-op (use --force-additional to add)",
                     Status.ADMIN_EXISTS)
            return EXIT_OK

        if force_additional:
            outcome = await insert_admin_forced(
                session, email=normalized, password_hash=password_hash, logger=log
            )
        else:
            outcome = await bootstrap_admin(
                session, email=normalized, password_hash=password_hash, logger=log
            )

    if outcome.status in (Status.ADMIN_CREATED, Status.ADMIN_EXISTS, Status.ALREADY_EXISTS):
        return EXIT_OK
    if outcome.status == Status.BOOTSTRAP_INVALID:
        return EXIT_INVALID
    return EXIT_DB_ERROR


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="create_admin", description="Create a platform admin (interactive)."
    )
    parser.add_argument("--email", default=_DEFAULT_EMAIL, help="admin email address")
    parser.add_argument(
        "--force-additional", action="store_true",
        help="create an additional admin even if one already exists",
    )
    args = parser.parse_args(argv)

    log = _build_logger()

    # Validate email early (before prompting) so an invalid email exits non-zero.
    if normalize_email(args.email) is None:
        log.error("%s reason=bad_email", Status.BOOTSTRAP_INVALID)
        return EXIT_INVALID

    try:
        password = _prompt_password()
    except ValueError as ex:
        # Never echo the password; only the non-secret reason.
        log.error("%s reason=weak_password (%s)", Status.BOOTSTRAP_INVALID, str(ex))
        return EXIT_INVALID
    except (EOFError, KeyboardInterrupt):
        log.error("%s reason=no_input", Status.BOOTSTRAP_INVALID)
        return EXIT_INVALID

    try:
        return asyncio.run(_run(args.email, args.force_additional, password, log))
    except Exception as ex:  # noqa: BLE001
        log.error("%s exc=%s", Status.BOOTSTRAP_DB_ERROR, type(ex).__name__)
        return EXIT_DB_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
