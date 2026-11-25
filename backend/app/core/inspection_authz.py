"""Authorization primitives for Gate 1 database transactions."""
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device_key import DeviceKey
from app.models.inspection_visit import InspectionVisit
from app.models.tenant_config import TenantConfig
from app.models.vendor import Vendor, VendorStatus
from app.models.vendor_client_association import AssociationStatus, VendorClientAssociation


async def lock_vendor_visit_access(
    db: AsyncSession, *, tenant_id: UUID, owner_client_id: UUID, vendor_id: str,
    visit_id: UUID, assignment_id: UUID, generation: int,
) -> InspectionVisit:
    """Authorize an authenticated vendor's visit on the caller's write transaction.

    Acquire locks in tenant, vendor, visit order. Keep the transaction open
    through the authorized write. Input identity comes from authentication.
    """
    if vendor_id == "REVIEW":
        raise HTTPException(404, "VISIT_NOT_FOUND")
    await lock_active_tenant(db, tenant_id)

    vendor_status = await db.scalar(
        select(Vendor.status).where(Vendor.tenant_id == tenant_id, Vendor.vendor_id == vendor_id)
        .with_for_update()
    )
    visit = await db.scalar(
        select(InspectionVisit).where(
            InspectionVisit.id == visit_id, InspectionVisit.tenant_id == tenant_id,
            InspectionVisit.owner_client_id == owner_client_id,
            InspectionVisit.vendor_id == vendor_id,
        ).with_for_update().execution_options(populate_existing=True)
    )
    if visit is None:
        raise HTTPException(404, "VISIT_NOT_FOUND")
    if vendor_status != VendorStatus.ACTIVE:
        raise HTTPException(403, "VENDOR_INACTIVE")
    check_generation(visit, assignment_id, generation)
    if visit.revoked_at is not None:
        raise HTTPException(403, "VISIT_REVOKED")
    return visit


async def lock_vendor_visit(
    db: AsyncSession, *, tenant_id: UUID, owner_client_id: UUID, vendor_id: str,
    visit_id: UUID, assignment_id: UUID, generation: int,
) -> InspectionVisit:
    """Authorize a new write. Submit replay uses the access-only helper first."""
    visit = await lock_vendor_visit_access(
        db, tenant_id=tenant_id, owner_client_id=owner_client_id, vendor_id=vendor_id,
        visit_id=visit_id, assignment_id=assignment_id, generation=generation,
    )
    await check_open_visit(db, visit)
    return visit


async def lock_active_tenant(db: AsyncSession, tenant_id: UUID) -> None:
    tenant_active = await db.scalar(
        select(TenantConfig.is_active).where(TenantConfig.tenant_id == tenant_id)
        .with_for_update(read=True)
    )
    if not tenant_active:
        raise HTTPException(403, "TENANT_INACTIVE")


def check_generation(visit: InspectionVisit, assignment_id: UUID, generation: int) -> None:
    if (visit.assignment_id, visit.generation) != (assignment_id, generation):
        raise HTTPException(409, "ASSIGNMENT_GENERATION_STALE")


async def check_open_visit(db: AsyncSession, visit: InspectionVisit) -> None:
    if visit.submitted_at is not None:
        raise HTTPException(409, "VISIT_ALREADY_SUBMITTED")
    if visit.revoked_at is not None:
        raise HTTPException(403, "VISIT_REVOKED")
    if await db.scalar(select(func.clock_timestamp())) > visit.expires_at:
        raise HTTPException(410, "VISIT_EXPIRED")


async def reassign_visit(
    db: AsyncSession, *, tenant_id: UUID, owner_client_id: UUID, visit_id: UUID,
    assignment_id: UUID, generation: int, new_vendor_id: str,
) -> InspectionVisit:
    """Replace an open assignment for an authenticated owner. Caller commits."""
    await lock_active_tenant(db, tenant_id)
    scope = (
        InspectionVisit.id == visit_id, InspectionVisit.tenant_id == tenant_id,
        InspectionVisit.owner_client_id == owner_client_id,
    )
    old_vendor_id = await db.scalar(select(InspectionVisit.vendor_id).where(*scope))
    if old_vendor_id is None:
        raise HTTPException(404, "VISIT_NOT_FOUND")

    vendors = {}
    for vendor_id in sorted({old_vendor_id, new_vendor_id}):
        vendor = await db.scalar(
            select(Vendor).where(Vendor.vendor_id == vendor_id, Vendor.tenant_id == tenant_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        vendors[vendor_id] = vendor

    visit = await db.scalar(
        select(InspectionVisit).where(*scope)
        .with_for_update().execution_options(populate_existing=True)
    )
    if visit is None:
        raise HTTPException(404, "VISIT_NOT_FOUND")
    check_generation(visit, assignment_id, generation)
    if visit.vendor_id != old_vendor_id:
        raise HTTPException(409, "ASSIGNMENT_GENERATION_STALE")
    await check_open_visit(db, visit)

    replacement = vendors[new_vendor_id]
    if replacement is None or replacement.status != VendorStatus.ACTIVE or new_vendor_id == "REVIEW":
        raise HTTPException(422, "VENDOR_NOT_ASSIGNABLE")
    if replacement.created_by_client_id != owner_client_id:
        association = await db.scalar(select(VendorClientAssociation.association_id).where(
            VendorClientAssociation.tenant_id == tenant_id,
            VendorClientAssociation.client_id == owner_client_id,
            VendorClientAssociation.vendor_id == new_vendor_id,
            VendorClientAssociation.status == AssociationStatus.ACTIVE,
        ).with_for_update(read=True))
        if association is None:
            raise HTTPException(422, "VENDOR_NOT_ASSIGNABLE")

    visit.vendor_id = new_vendor_id
    visit.assignment_id = uuid4()
    visit.generation += 1
    await db.flush()
    return visit


async def revoke_visit(
    db: AsyncSession, *, tenant_id: UUID, owner_client_id: UUID, visit_id: UUID,
    assignment_id: UUID, generation: int,
) -> None:
    """Revoke a visit for its authenticated owner. Caller commits."""
    await lock_active_tenant(db, tenant_id)
    visit = await db.scalar(
        select(InspectionVisit).where(
            InspectionVisit.id == visit_id, InspectionVisit.tenant_id == tenant_id,
            InspectionVisit.owner_client_id == owner_client_id,
        ).with_for_update().execution_options(populate_existing=True)
    )
    if visit is None:
        raise HTTPException(404, "VISIT_NOT_FOUND")
    check_generation(visit, assignment_id, generation)
    if visit.revoked_at is None:
        await check_open_visit(db, visit)
        visit.revoked_at = await db.scalar(select(func.clock_timestamp()))


async def revoke_inspection_key(
    db: AsyncSession, *, tenant_id: UUID, vendor_id: str, key_id: UUID,
) -> None:
    """Revoke a signing key for Gate 1, serialized with visit authorization."""
    locked_vendor = await db.scalar(
        select(Vendor.vendor_id).where(
            Vendor.vendor_id == vendor_id, Vendor.tenant_id == tenant_id,
        ).with_for_update()
    )
    if locked_vendor is None:
        raise HTTPException(404, "INSPECTION_KEY_NOT_FOUND")
    key = await db.scalar(
        select(DeviceKey).where(
            DeviceKey.key_id == key_id, DeviceKey.tenant_id == tenant_id,
            DeviceKey.vendor_id == vendor_id, DeviceKey.inspection_enrollment_id.is_not(None),
        ).execution_options(populate_existing=True)
    )
    if key is None:
        raise HTTPException(404, "INSPECTION_KEY_NOT_FOUND")
    if key.revoked_at is None:
        key.revoked_at = await db.scalar(select(func.clock_timestamp()))


async def require_receipt_key(
    db: AsyncSession, *, visit: InspectionVisit, key_id: UUID, received_at: datetime,
) -> DeviceKey:
    """Check a key against trusted receipt time while holding the vendor visit lock."""
    key = await db.scalar(
        select(DeviceKey).where(
            DeviceKey.key_id == key_id, DeviceKey.tenant_id == visit.tenant_id,
            DeviceKey.vendor_id == visit.vendor_id, DeviceKey.inspection_enrollment_id.is_not(None),
        ).execution_options(populate_existing=True)
    )
    if key is not None and key.revoked_at is not None:
        raise HTTPException(422, "EVIDENCE_KEY_REVOKED")
    if key is None or received_at < key.active_from or (
        key.active_to is not None and received_at >= key.active_to
    ):
        raise HTTPException(422, "CAPTURE_KEY_INELIGIBLE")
    return key
