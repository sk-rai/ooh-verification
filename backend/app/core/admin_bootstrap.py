"""Admin bootstrap: testable, concurrency-safe initial-admin creation.

Spec: .kiro/specs/admin-seed-credential-fix (Phase B, design.md Section B).

Two layers:
  * ``bootstrap_admin(session, email, password_hash, logger) -> Outcome`` -- a pure,
    testable async function. It takes an explicit AsyncSession, NEVER reads
    ``DATABASE_URL`` and NEVER reads environment itself.
  * A deploy entry point (``python -m app.core.admin_bootstrap``) -- the ONLY code
    here that builds a session from ``DATABASE_URL`` and reads the two bootstrap env
    vars. It always exits 0 so the service never crash-loops.

Secret hygiene (hard rule)
--------------------------
This module NEVER logs or prints a password, a password hash, or an email VALUE.
Log lines carry only a machine-greppable status code, a reason code, or an exception
CLASS NAME. There is no hardcoded credential anywhere in this module.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError, SQLAlchemyError


# =============================================================================
# Status codes (string constants; greppable, non-secret).
# =============================================================================
class Status:
    ADMIN_EXISTS = "ADMIN_EXISTS"
    BOOTSTRAP_ENV_STILL_SET = "BOOTSTRAP_ENV_STILL_SET"
    NO_ADMIN_NO_BOOTSTRAP = "NO_ADMIN_NO_BOOTSTRAP"
    BOOTSTRAP_INVALID = "BOOTSTRAP_INVALID"
    ADMIN_CREATED = "ADMIN_CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    BOOTSTRAP_DB_ERROR = "BOOTSTRAP_DB_ERROR"


@dataclass(frozen=True)
class Outcome:
    """Result of a bootstrap attempt. Carries only non-secret tokens.

    ``status`` is one of :class:`Status`. ``reason`` (for BOOTSTRAP_INVALID) is a
    short reason code, never a value. ``exc`` (for BOOTSTRAP_DB_ERROR) is an
    exception CLASS NAME only. ``str(outcome)`` yields a greppable one-liner.
    """

    status: str
    reason: Optional[str] = None
    exc: Optional[str] = None

    def __str__(self) -> str:  # greppable, secret-free
        parts = [self.status]
        if self.reason:
            parts.append(f"reason={self.reason}")
        if self.exc:
            parts.append(f"exc={self.exc}")
        return " ".join(parts)


# Fixed advisory-lock key for serialising empty-table bootstrap across instances.
# Arbitrary stable int64 constant (not a secret). "admin-bootstrap" -> this number.
_ADVISORY_LOCK_KEY = 7345019283746501

# Short timeouts (ms) so a stuck lock can never hang boot.
_LOCK_TIMEOUT_MS = 5000
_STATEMENT_TIMEOUT_MS = 5000


# =============================================================================
# Pure-string validators (NO passlib internals).
# =============================================================================

# bcrypt base64 alphabet (NOT standard base64): ./A-Za-z0-9
_BCRYPT_B64_CHARS = set(
    "./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
)

# Minimal, pragmatic email format check (not a full RFC validator).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_bcrypt_hash(s: object) -> bool:
    """Pure-string bcrypt hash check. Accept ``$2b$``/``$2a$``, length 60, cost
    10-14 inclusive, and only bcrypt-base64 characters in the salt+digest body.

    Does NOT import or call passlib/bcrypt. Returns ``False`` for anything not a
    well-formed string of the expected shape.
    """
    if not isinstance(s, str) or len(s) != 60:
        return False
    if s[:4] not in ("$2b$", "$2a$"):
        return False
    # Format: $2b$CC$<22-char salt><31-char digest>  -> cost is chars 4,5; '$' at 6.
    if s[6] != "$":
        return False
    cost_str = s[4:6]
    if not cost_str.isdigit():
        return False
    cost = int(cost_str)
    if cost < 10 or cost > 14:
        return False
    body = s[7:]  # 53 chars of bcrypt-base64
    if len(body) != 53:
        return False
    return all(ch in _BCRYPT_B64_CHARS for ch in body)


# Backwards/alias-friendly names the contract tests may probe for.
def is_valid_bcrypt_hash(s: object) -> bool:
    """Alias for :func:`valid_bcrypt_hash` (same pure-string check)."""
    return valid_bcrypt_hash(s)


def normalize_email(e: object) -> Optional[str]:
    """Strip + lowercase + basic format check. Return the normalized email or
    ``None`` if it is not a plausibly valid address. Never logs the value.
    """
    if not isinstance(e, str):
        return None
    candidate = e.strip().lower()
    if not candidate or not _EMAIL_RE.match(candidate):
        return None
    return candidate


# Alias (British spelling) in case the contract probes for it.
def normalise_email(e: object) -> Optional[str]:
    """Alias for :func:`normalize_email`."""
    return normalize_email(e)


def _invalid_reason(email: Optional[str], password_hash: Optional[str]) -> Optional[str]:
    """Return a reason code if (email, password_hash) are INVALID, else ``None``.

    Partial configuration (exactly one of the two provided) is INVALID, not absent.
    Reason codes are non-secret tokens only.
    """
    has_email = email is not None and str(email).strip() != ""
    has_hash = password_hash is not None and str(password_hash) != ""

    # Both absent -> not "invalid"; the caller treats that as ABSENT.
    if not has_email and not has_hash:
        return None

    if has_email != has_hash:
        return "partial_config"

    if normalize_email(email) is None:
        return "bad_email"

    if not valid_bcrypt_hash(password_hash):
        # Distinguish a few common bcrypt defects for a useful (non-secret) reason.
        h = password_hash if isinstance(password_hash, str) else ""
        if len(h) != 60:
            return "bad_length"
        if h[:4] not in ("$2b$", "$2a$"):
            return "bad_prefix"
        cost_str = h[4:6] if len(h) >= 6 else ""
        if cost_str.isdigit() and not (10 <= int(cost_str) <= 14):
            return "cost_out_of_range"
        return "bad_charset"

    return None


# =============================================================================
# Core testable function.
# =============================================================================


async def _admin_table_nonempty(session) -> bool:
    result = await session.execute(text("SELECT 1 FROM admin_users LIMIT 1"))
    return result.first() is not None


async def bootstrap_admin(session, email=None, password_hash=None, logger=None) -> Outcome:
    """Create the initial admin ONLY from an explicit, valid bootstrap secret.

    Behaviour (design.md Section B):
      * Admin row(s) already exist -> ``ADMIN_EXISTS`` (no write). If BOTH bootstrap
        inputs are also present, additionally emit a WARNING ``BOOTSTRAP_ENV_STILL_SET``.
      * Empty table AND no bootstrap inputs -> ``NO_ADMIN_NO_BOOTSTRAP`` (WARNING, no write).
      * Empty table AND inputs present but invalid -> ``BOOTSTRAP_INVALID`` reason=<code>
        (ERROR, no write).
      * Empty table AND valid -> concurrency-safe insert of exactly one AdminUser
        (name="System Admin", is_active=True, supplied hash) -> ``ADMIN_CREATED``.

    Never logs/prints the email value or the hash. ``session`` is an explicit
    AsyncSession; this function never reads ``DATABASE_URL`` or the environment.
    """
    log = logger or logging.getLogger(__name__)

    has_email = email is not None and str(email).strip() != ""
    has_hash = password_hash is not None and str(password_hash) != ""
    both_inputs_present = has_email and has_hash
    any_input_present = has_email or has_hash

    # 1) Existing admin short-circuit (no write).
    try:
        if await _admin_table_nonempty(session):
            if any_input_present:
                log.warning(
                    "%s: admin already exists but bootstrap inputs are still set; "
                    "remove them (no values shown)", Status.BOOTSTRAP_ENV_STILL_SET
                )
            else:
                log.info("%s: Admin user exists", Status.ADMIN_EXISTS)
            return Outcome(Status.ADMIN_EXISTS)
    except (OperationalError, ProgrammingError, SQLAlchemyError) as ex:
        await _safe_rollback(session)
        log.error("%s exc=%s", Status.BOOTSTRAP_DB_ERROR, type(ex).__name__)
        return Outcome(Status.BOOTSTRAP_DB_ERROR, exc=type(ex).__name__)

    # 2) Empty table, no inputs -> absent.
    if not any_input_present:
        log.warning("%s: admin_users empty and no bootstrap secret provided; "
                    "created nothing", Status.NO_ADMIN_NO_BOOTSTRAP)
        return Outcome(Status.NO_ADMIN_NO_BOOTSTRAP)

    # 3) Empty table, inputs present -> validate.
    reason = _invalid_reason(email, password_hash)
    if reason is not None:
        log.error("%s reason=%s: bootstrap config rejected (no values shown)",
                  Status.BOOTSTRAP_INVALID, reason)
        return Outcome(Status.BOOTSTRAP_INVALID, reason=reason)

    normalized_email = normalize_email(email)

    # 4) Concurrency-safe insert inside one transaction.
    return await _locked_insert(session, normalized_email, password_hash, log)


async def _safe_rollback(session) -> None:
    try:
        await session.rollback()
    except Exception:  # noqa: BLE001 - best-effort; never raise from cleanup
        pass


async def _locked_insert(session, normalized_email, password_hash, log) -> Outcome:
    """Advisory-lock + emptiness-recheck + single insert, mapped to an Outcome."""
    import uuid
    from datetime import datetime, timezone

    try:
        # Short timeouts so a stuck lock cannot hang boot (best-effort; some
        # dialects/sessions may ignore SET LOCAL outside a tx -- harmless).
        await session.execute(text(f"SET LOCAL lock_timeout = '{_LOCK_TIMEOUT_MS}ms'"))
        await session.execute(
            text(f"SET LOCAL statement_timeout = '{_STATEMENT_TIMEOUT_MS}ms'")
        )

        # Serialise empty-table bootstrap across instances/connections.
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ADVISORY_LOCK_KEY}
        )

        # Re-check emptiness INSIDE the lock.
        if await _admin_table_nonempty(session):
            await session.commit()  # release the advisory lock
            log.info("%s: another instance created the admin first", Status.ALREADY_EXISTS)
            return Outcome(Status.ALREADY_EXISTS)

        now = datetime.now(tz=timezone.utc)
        await session.execute(
            text(
                "INSERT INTO admin_users "
                "(admin_id, email, password_hash, name, is_active, created_at, updated_at) "
                "VALUES (:admin_id, :email, :password_hash, :name, true, :created_at, :updated_at)"
            ),
            {
                "admin_id": uuid.uuid4(),
                "email": normalized_email,
                "password_hash": password_hash,
                "name": "System Admin",
                "created_at": now,
                "updated_at": now,
            },
        )
        await session.commit()
        log.info("%s: initial admin created (no values shown)", Status.ADMIN_CREATED)
        return Outcome(Status.ADMIN_CREATED)

    except IntegrityError as ex:  # racing duplicate email (UNIQUE constraint)
        await _safe_rollback(session)
        log.info("%s: racing duplicate insert mapped from %s",
                 Status.ALREADY_EXISTS, type(ex).__name__)
        return Outcome(Status.ALREADY_EXISTS)
    except (OperationalError, ProgrammingError, SQLAlchemyError) as ex:
        await _safe_rollback(session)
        log.error("%s exc=%s", Status.BOOTSTRAP_DB_ERROR, type(ex).__name__)
        return Outcome(Status.BOOTSTRAP_DB_ERROR, exc=type(ex).__name__)


async def insert_admin_forced(session, email=None, password_hash=None, logger=None) -> Outcome:
    """Validate and insert an admin even when the table is non-empty (CLI --force).

    Shares the SAME validator and insert path as :func:`bootstrap_admin`, but skips
    the empty-table short-circuit. A duplicate email maps to ``ALREADY_EXISTS``.
    Returns ``BOOTSTRAP_INVALID`` for bad/absent config. Never logs values.
    """
    log = logger or logging.getLogger(__name__)

    reason = _invalid_reason(email, password_hash)
    has_email = email is not None and str(email).strip() != ""
    has_hash = password_hash is not None and str(password_hash) != ""
    if reason is None and not (has_email and has_hash):
        reason = "partial_config"
    if reason is not None:
        log.error("%s reason=%s: bootstrap config rejected (no values shown)",
                  Status.BOOTSTRAP_INVALID, reason)
        return Outcome(Status.BOOTSTRAP_INVALID, reason=reason)

    normalized_email = normalize_email(email)
    import uuid
    from datetime import datetime, timezone

    try:
        now = datetime.now(tz=timezone.utc)
        await session.execute(
            text(
                "INSERT INTO admin_users "
                "(admin_id, email, password_hash, name, is_active, created_at, updated_at) "
                "VALUES (:admin_id, :email, :password_hash, :name, true, :created_at, :updated_at)"
            ),
            {
                "admin_id": uuid.uuid4(),
                "email": normalized_email,
                "password_hash": password_hash,
                "name": "System Admin",
                "created_at": now,
                "updated_at": now,
            },
        )
        await session.commit()
        log.info("%s: additional admin created (no values shown)", Status.ADMIN_CREATED)
        return Outcome(Status.ADMIN_CREATED)
    except IntegrityError as ex:
        await _safe_rollback(session)
        log.info("%s: duplicate email mapped from %s",
                 Status.ALREADY_EXISTS, type(ex).__name__)
        return Outcome(Status.ALREADY_EXISTS)
    except (OperationalError, ProgrammingError, SQLAlchemyError) as ex:
        await _safe_rollback(session)
        log.error("%s exc=%s", Status.BOOTSTRAP_DB_ERROR, type(ex).__name__)
        return Outcome(Status.BOOTSTRAP_DB_ERROR, exc=type(ex).__name__)


# =============================================================================
# Deploy entry point. The ONLY place that reads DATABASE_URL / env. Always exit 0.
# =============================================================================


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("admin_bootstrap")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


async def _run_deploy() -> Outcome:
    """Build a session from DATABASE_URL, read bootstrap env, run bootstrap_admin."""
    from app.core.database import AsyncSessionLocal  # bound to DATABASE_URL at import

    log = _build_logger()
    email = os.environ.get("ADMIN_BOOTSTRAP_EMAIL")
    password_hash = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD_HASH")

    async with AsyncSessionLocal() as session:
        return await bootstrap_admin(
            session, email=email, password_hash=password_hash, logger=log
        )


def main() -> int:
    """Deploy entry: ALWAYS return 0 so the service never crash-loops."""
    log = _build_logger()
    try:
        outcome = asyncio.run(_run_deploy())
        log.info("admin bootstrap finished: %s", outcome)
    except Exception as ex:  # noqa: BLE001 - deploy path must never crash the service
        log.error("%s exc=%s (deploy path swallowed to keep service up)",
                  Status.BOOTSTRAP_DB_ERROR, type(ex).__name__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
