"""
Device key versioning service.

Core logic for the key-rotation fix (see web/demo-shots/KEY_VERSIONING_DESIGN.md):
  - compute a canonical key fingerprint (shared contract with Android),
  - append a new key version on (re-)registration without destroying old keys,
  - look up the key active at a given capture time,
  - verify a signature against the correct historical key (or any known key).

All functions are async and take an AsyncSession. Nothing here hard-rejects; the
caller decides how to treat the verification outcome (warn-mode by default).
"""
import base64
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device_key import DeviceKey
from app.services.signature_verification import SignatureVerificationService

logger = logging.getLogger(__name__)


# ── Fingerprint (shared contract with Android) ───────────────────────────────
# Single source of truth is SignatureVerificationService.public_key_fingerprint:
#   fingerprint = lowercase-hex SHA-256 of the DER SubjectPublicKeyInfo bytes
#   (== Android's SHA-256 over publicKey.encoded). We delegate to it to avoid two
#   divergent implementations.
def compute_key_fingerprint(public_key_pem: str) -> str:
    """Canonical SHA-256 fingerprint of a PEM public key (hex of DER SPKI).

    Delegates to SignatureVerificationService.public_key_fingerprint (shared
    cross-component contract). Falls back to a normalized-PEM hash only if that
    returns empty (unparseable key) so the row still gets a stable, traceable id.
    """
    fp = SignatureVerificationService.public_key_fingerprint(public_key_pem)
    if fp:
        return fp
    normalized = "".join(public_key_pem.split())
    return hashlib.sha256(normalized.encode()).hexdigest()


# ── Registration: append, never overwrite ───────────────────────────────────
async def register_key_version(
    db: AsyncSession,
    *,
    vendor_id: str,
    tenant_id,
    device_id: Optional[str],
    public_key_pem: str,
    algorithm: str = "ECDSA-P256",
    now: Optional[datetime] = None,
) -> Tuple[DeviceKey, bool]:
    """
    Append-or-reuse a device key version for a vendor.

    - If the vendor's current ACTIVE key has the same fingerprint -> no-op (reuse).
    - Otherwise: retire the current active key (active_to = now) and insert the new
      one as active. Never deletes a prior key.

    Returns (active_device_key_row, created_new: bool). Does not commit.
    """
    now = now or datetime.now(tz=timezone.utc)
    fp = compute_key_fingerprint(public_key_pem)

    # current active key (active_to IS NULL), newest first
    res = await db.execute(
        select(DeviceKey)
        .where(DeviceKey.vendor_id == vendor_id, DeviceKey.active_to.is_(None))
        .order_by(DeviceKey.active_from.desc())
    )
    active_keys = res.scalars().all()

    # If an active key already matches this fingerprint, reuse (idempotent).
    for ak in active_keys:
        if ak.key_fingerprint == fp:
            return ak, False

    # Retire any currently-active keys for this vendor.
    for ak in active_keys:
        ak.active_to = now

    new_key = DeviceKey(
        vendor_id=vendor_id,
        tenant_id=tenant_id,
        device_id=device_id,
        public_key=public_key_pem,
        algorithm=algorithm,
        key_fingerprint=fp,
        active_from=now,
        active_to=None,
    )
    db.add(new_key)
    logger.info(f"[device_key] vendor={vendor_id} registered new key fp={fp[:12]}… "
                f"(retired {len(active_keys)} active)")
    return new_key, True


async def get_keys_for_vendor(db: AsyncSession, vendor_id: str) -> List[DeviceKey]:
    """All known key versions for a vendor, newest active_from first."""
    res = await db.execute(
        select(DeviceKey).where(DeviceKey.vendor_id == vendor_id)
        .order_by(DeviceKey.active_from.desc())
    )
    return list(res.scalars().all())


def _key_active_at(keys: List[DeviceKey], when: Optional[datetime]) -> Optional[DeviceKey]:
    if when is None:
        # No capture time -> prefer the currently-active key.
        for k in keys:
            if k.active_to is None:
                return k
        return keys[0] if keys else None
    for k in keys:
        start = k.active_from
        end = k.active_to
        if start is not None and when < start:
            continue
        if end is not None and when >= end:
            continue
        return k
    return None


# ── Verification against the correct historical key ──────────────────────────
def _parse_sig_field(raw) -> Tuple[Optional[str], Optional[str]]:
    if not raw:
        return None, None
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            o = json.loads(raw)
            return o.get("signature"), o.get("algorithm")
        except json.JSONDecodeError:
            return None, None
    return raw, None


async def verify_against_history(
    db: AsyncSession,
    *,
    vendor_id: str,
    photo_hash_hex: str,
    signature_field: str,
    capture_time: Optional[datetime] = None,
) -> dict:
    """
    Verify a signature against the vendor's key history.

    Strategy:
      1. Try the key active at capture_time first (if determinable).
      2. Fall back to trying ALL known keys (newest first) — covers clock skew and
         the brief regenerate-mid-session window.

    Returns a dict:
      {
        "outcome": "verified" | "unverifiable_rotated" | "invalid" | "no_keys",
        "matched_key_id": <uuid or None>,
        "matched_fingerprint": <hex or None>,
      }

    Outcome semantics (warn-mode friendly; caller decides enforcement):
      - verified             : signature validated against a known registered key.
      - invalid              : vendor HAS key(s) covering this capture, none verified
                               -> genuine mismatch/tamper candidate.
      - unverifiable_rotated : vendor has key(s) but none cover the capture window
                               AND none verify -> likely signed under a key no longer
                               retained (key rotated). NOT fraud.
      - no_keys              : vendor has no registered keys at all.
    """
    sig_b64, _algo_field = _parse_sig_field(signature_field)
    keys = await get_keys_for_vendor(db, vendor_id)
    if not keys:
        return {"outcome": "no_keys", "matched_key_id": None, "matched_fingerprint": None}
    if not (sig_b64 and photo_hash_hex):
        return {"outcome": "invalid", "matched_key_id": None, "matched_fingerprint": None}

    try:
        sig_bytes = base64.b64decode(sig_b64)
        photo_hash = bytes.fromhex(photo_hash_hex)
    except Exception:
        return {"outcome": "invalid", "matched_key_id": None, "matched_fingerprint": None}

    def _try(k: DeviceKey) -> bool:
        try:
            return SignatureVerificationService.verify_signature(
                photo_hash=photo_hash, signature=sig_bytes,
                public_key=k.public_key, algorithm=k.algorithm or "ECDSA-P256",
            )
        except Exception:
            return False

    # 1. key active at capture time
    primary = _key_active_at(keys, capture_time)
    if primary and _try(primary):
        return {"outcome": "verified", "matched_key_id": str(primary.key_id),
                "matched_fingerprint": primary.key_fingerprint}

    # 2. any known key
    for k in keys:
        if primary is not None and k.key_id == primary.key_id:
            continue
        if _try(k):
            return {"outcome": "verified", "matched_key_id": str(k.key_id),
                    "matched_fingerprint": k.key_fingerprint}

    # Nothing matched. Distinguish "covered window but failed" (invalid) from
    # "no key covers this capture" (rotated/unretained).
    covered = _key_active_at(keys, capture_time) is not None
    return {
        "outcome": "invalid" if covered else "unverifiable_rotated",
        "matched_key_id": None,
        "matched_fingerprint": None,
    }
