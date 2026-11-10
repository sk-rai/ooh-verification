"""Administrator-only password-state fingerprint for JWT session invalidation.

Spec: .kiro/specs/admin-seed-credential-fix Phase C

Design
------
When an administrator token is issued (POST /api/admin/login), a short
HMAC-SHA256 fingerprint of the stored password_hash is embedded as the
``pwf`` claim.  get_current_admin re-computes the fingerprint from the DB
row on every request and rejects the token if it does not match.

Effect
------
- Any password change automatically invalidates all prior administrator JWTs
  because the stored hash changes, so the expected fingerprint changes.
- Client and vendor tokens are unaffected — they never carry pwf.
- JWT_SECRET_KEY rotation also invalidates all tokens (unchanged behaviour).

Cryptographic construction
--------------------------
    domain   = b"admin-pwf-v1:"          (domain-separation prefix)
    message  = domain + password_hash.encode("utf-8")
    digest   = HMAC-SHA256(key=JWT_SECRET_KEY, msg=message)[:16]
    pwf      = base64url(digest, no padding)   # 22 ASCII chars

HMAC (not a bare hash) so the fingerprint cannot be forged even if the
bcrypt hash is leaked.  SHA-256 truncated to 128 bits is infeasible to
brute-force.  The domain prefix prevents cross-purpose collisions.

Insecure-key guard
------------------
If JWT_SECRET_KEY equals the known insecure in-code default, compute_pwf()
and verify_pwf() raise RuntimeError.  Administrator login returns HTTP 500,
making the misconfiguration immediately visible without silently accepting
forgeable fingerprints.

Secret hygiene
--------------
This module NEVER logs, prints or embeds a password, password hash or key.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Optional

# Same env-var and fallback as security.py.  Imported separately to keep
# this module self-contained and testable without importing the full
# security module.
def _get_jwt_secret_key() -> str:
    """Read JWT_SECRET_KEY lazily at call time so test env-var overrides work."""
    return os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")

# Known insecure in-code defaults to refuse at runtime.
_INSECURE_DEFAULTS: frozenset = frozenset({
    "your-secret-key-change-in-production",
    "jwt-secret-key-change-in-production",
    "dev-secret-key-change-in-production",
    "secret",
    "",
})

# Domain-separation prefix — must match between issuance and validation.
_DOMAIN_PREFIX: bytes = b"admin-pwf-v1:"

# Claim name embedded in the JWT payload.
PWF_CLAIM: str = "pwf"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def compute_pwf(password_hash: str, secret_key: Optional[str] = None) -> str:
    """Compute the password-state fingerprint for an administrator JWT.

    Args:
        password_hash: The bcrypt hash stored in admin_users.password_hash.
            This is a 60-char ASCII string — never logged or returned.
        secret_key: Override for tests.  Defaults to JWT_SECRET_KEY.

    Returns:
        22-char base64url string (no padding) from 16 bytes of HMAC-SHA256.

    Raises:
        TypeError:    password_hash is not a non-empty str.
        ValueError:   password_hash does not look like a bcrypt hash.
        RuntimeError: secret_key equals a known insecure default.
    """
    key = secret_key if secret_key is not None else _get_jwt_secret_key()
    _reject_insecure_key(key)
    _validate_password_hash(password_hash)
    message = _DOMAIN_PREFIX + password_hash.encode("utf-8")
    raw = hmac.new(key.encode("utf-8"), message, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def verify_pwf(
    token_pwf: object,
    password_hash: str,
    secret_key: Optional[str] = None,
) -> bool:
    """Verify the ``pwf`` claim extracted from an administrator JWT.

    Performs constant-time comparison.  Returns False for any mismatch,
    missing claim, wrong type, or malformed value — callers raise HTTP 401.

    Args:
        token_pwf: The raw value of the ``pwf`` key from the decoded payload.
            May be None, non-string, or malformed — all yield False.
        password_hash: Current value from admin_users.password_hash.
        secret_key: Override for tests.

    Returns:
        True only if token_pwf is a non-empty str and equals compute_pwf().

    Raises:
        RuntimeError: secret_key equals a known insecure default.
    """
    if not isinstance(token_pwf, str) or not token_pwf:
        return False
    key = secret_key if secret_key is not None else _get_jwt_secret_key()
    _reject_insecure_key(key)
    try:
        _validate_password_hash(password_hash)
        expected = compute_pwf(password_hash, secret_key=key)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(token_pwf, expected)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _reject_insecure_key(key: str) -> None:
    if key in _INSECURE_DEFAULTS:
        raise RuntimeError(
            "JWT_SECRET_KEY is absent or equals an insecure default. "
            "Set JWT_SECRET_KEY in the environment before using admin fingerprints."
        )


def _validate_password_hash(password_hash: str) -> None:
    if not isinstance(password_hash, str) or not password_hash:
        raise TypeError("password_hash must be a non-empty str")
    if not (password_hash.startswith(("$2b$", "$2a$")) and len(password_hash) == 60):
        raise ValueError(
            "password_hash does not look like a valid bcrypt hash "
            "(expected $2b$/$2a$ prefix and length 60)"
        )
