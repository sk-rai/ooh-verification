"""Verify original bytes for a Gate 1 receipt under its authorization locks."""
from base64 import b64decode
from binascii import Error as Base64Error
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.inspection_authz import require_receipt_key
from app.models.inspection_visit import InspectionVisit
from app.services.signature_verification import SignatureVerificationService


@dataclass(frozen=True)
class VerifiedInspectionOriginal:
    digest: str
    byte_length: int
    key_id: UUID
    key_fingerprint: str
    received_at: datetime
    method: str = "ECDSA-P256-SHA256-HEX"


async def verify_inspection_original(
    db: AsyncSession, *, visit: InspectionVisit, key_id: UUID,
    received_at: datetime, deadline: datetime, original: bytes, expected_digest: str,
    expected_length: int, signature_b64: str,
) -> VerifiedInspectionOriginal:
    """Verify bytes against an authorized reservation and a server receipt time.

    The caller holds the tenant, vendor and visit locks, resolves the exact
    reservation, and commits the positive result with the evidence and replay row.
    """
    if received_at > deadline:
        raise HTTPException(410, "VISIT_EXPIRED")
    digest = sha256(original).digest()
    if not original or len(original) != expected_length or digest.hex() != expected_digest:
        raise HTTPException(422, "CAPTURE_CONTENT_MISMATCH")
    key = await require_receipt_key(db, visit=visit, key_id=key_id, received_at=received_at)
    try:
        signature = b64decode(signature_b64, validate=True)
    except (Base64Error, ValueError):
        raise HTTPException(422, "CAPTURE_SIGNATURE_INVALID") from None
    if key.algorithm != "ECDSA-P256" or not SignatureVerificationService.verify_signature(
        digest, signature, key.public_key, key.algorithm,
    ):
        raise HTTPException(422, "CAPTURE_SIGNATURE_INVALID")

    return VerifiedInspectionOriginal(
        digest=digest.hex(), byte_length=len(original), key_id=key.key_id,
        key_fingerprint=key.key_fingerprint, received_at=received_at,
    )
