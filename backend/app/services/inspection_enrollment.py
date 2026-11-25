"""Trusted Gate 1 device enrollment, separate from legacy key rotation."""
from datetime import timedelta
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.inspection_authz import lock_active_tenant
from app.core.security import create_access_token, decode_access_token, verify_ecdsa_signature
from app.models.device_key import DeviceKey
from app.models.vendor import Vendor, VendorStatus
from app.schemas.auth import InspectionDeviceEnrollment
from app.services.device_key_service import compute_key_fingerprint


def issue_enrollment_proof(vendor: Vendor) -> str:
    """Call after real OTP verification, while holding the tenant and vendor locks."""
    vendor.inspection_enrollment_nonce = uuid4()
    return create_access_token({
        "type": "inspection_enrollment", "sub": vendor.vendor_id,
        "tenant_id": str(vendor.tenant_id), "device_id": vendor.device_id,
        "jti": str(vendor.inspection_enrollment_nonce),
    }, expires_delta=timedelta(minutes=5))


async def enroll_inspection_device(
    db: AsyncSession, *, actor: Vendor, data: InspectionDeviceEnrollment,
) -> DeviceKey:
    """Consume OTP-backed proof and persist one trusted key. Caller commits."""
    tenant_id, vendor_id = actor.tenant_id, actor.vendor_id
    if vendor_id == "REVIEW":
        raise HTTPException(403, "VENDOR_INACTIVE")
    await lock_active_tenant(db, tenant_id)
    vendor = await db.scalar(
        select(Vendor).where(Vendor.vendor_id == vendor_id, Vendor.tenant_id == tenant_id)
        .with_for_update().execution_options(populate_existing=True)
    )
    if vendor is None or vendor.status != VendorStatus.ACTIVE:
        raise HTTPException(403, "VENDOR_INACTIVE")

    proof = decode_access_token(data.enrollment_proof) or {}
    if (not vendor.device_verified or vendor.device_id != data.device_id
            or vendor.inspection_enrollment_nonce is None
            or proof.get("type") != "inspection_enrollment"
            or proof.get("sub") != vendor_id or proof.get("tenant_id") != str(tenant_id)
            or proof.get("device_id") != data.device_id
            or proof.get("jti") != str(vendor.inspection_enrollment_nonce)):
        raise HTTPException(403, "INSPECTION_ENROLLMENT_PROOF_INVALID")

    try:
        key = serialization.load_pem_public_key(data.public_key.encode())
    except (ValueError, TypeError):
        raise HTTPException(422, "INSPECTION_PUBLIC_KEY_INVALID") from None
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
        raise HTTPException(422, "INSPECTION_PUBLIC_KEY_INVALID")
    if not verify_ecdsa_signature(data.public_key, data.enrollment_proof, data.proof_signature):
        raise HTTPException(422, "INSPECTION_KEY_POSSESSION_INVALID")
    fingerprint = compute_key_fingerprint(data.public_key)
    trusted_scope = (
        DeviceKey.tenant_id == tenant_id, DeviceKey.vendor_id == vendor_id,
        DeviceKey.inspection_enrollment_id.is_not(None),
    )
    if await db.scalar(select(DeviceKey.key_id).where(
        *trusted_scope, DeviceKey.key_fingerprint == fingerprint, DeviceKey.revoked_at.is_not(None),
    ).limit(1)):
        raise HTTPException(422, "EVIDENCE_KEY_REVOKED")

    now = await db.scalar(select(func.clock_timestamp()))
    active_keys = (await db.scalars(select(DeviceKey).where(
        *trusted_scope, DeviceKey.active_to.is_(None),
    ))).all()
    for current in active_keys:
        current.active_to = now
    record = DeviceKey(
        tenant_id=tenant_id, vendor_id=vendor_id, device_id=data.device_id,
        public_key=data.public_key, key_fingerprint=fingerprint, active_from=now,
        inspection_enrollment_id=vendor.inspection_enrollment_nonce,
    )
    vendor.inspection_enrollment_nonce = None
    db.add(record)
    await db.flush()
    return record
