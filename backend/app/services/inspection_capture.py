"""Assigned visit packages and exact photo reservation writes."""
from datetime import datetime
from uuid import UUID, uuid4, uuid5

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.inspection_authz import check_open_visit, lock_vendor_visit, lock_vendor_visit_access
from app.models.evidence import Evidence
from app.models.inspection_visit import InspectionVisit
from app.models.vendor import Vendor
from app.services.inspection_original_storage import InspectionOriginalStorage
from app.services.inspection_receipt import verify_inspection_original
from app.schemas.inspection_capture import (
    InspectionCaptureRequest, InspectionCaptureReservation, InspectionPackage,
    InspectionPackageDocument, InspectionCaptureFinalize, InspectionCaptureResult,
)


async def reserve_inspection_upload(
    db: AsyncSession, *, actor: Vendor, visit_id: UUID, request: InspectionCaptureRequest,
) -> InspectionCaptureReservation:
    visit = await lock_vendor_visit(
        db, tenant_id=actor.tenant_id, vendor_id=actor.vendor_id, visit_id=visit_id,
        owner_client_id=request.owner_client_id, assignment_id=request.assignment_id,
        generation=request.generation,
    )
    await require_capture_package(db, visit)
    params = request.model_dump() | {"visit_id": visit.id}
    existing = (await db.execute(text("""
        SELECT r.id, r.deadline, r.client_capture_id, r.upload_key, r.digest, r.byte_length,
               t.document_instance_id, t.field_id, t.slot_id, t.repeat_item_id
        FROM inspection_upload_reservation AS r
        JOIN inspection_capture_target AS t ON t.id = r.target_id
        WHERE r.assignment_id = :assignment_id
          AND (r.upload_key = :upload_key OR r.client_capture_id = :client_capture_id)
    """), params)).mappings().all()
    if existing:
        if len(existing) != 1 or any(
            params[k] != v for k, v in existing[0].items() if k not in ("id", "deadline")
        ):
            raise HTTPException(409, "IDEMPOTENCY_PAYLOAD_MISMATCH")
        reservation_id = existing[0]["id"]
        deadline = existing[0]["deadline"]
    else:
        target_id = await db.scalar(text("""
            SELECT id FROM inspection_capture_target
            WHERE visit_id = :visit_id AND document_instance_id = :document_instance_id
              AND field_id = :field_id AND slot_id = :slot_id
              AND repeat_item_id IS NOT DISTINCT FROM CAST(:repeat_item_id AS uuid)
        """), params)
        if target_id is None:
            raise HTTPException(422, "INVALID_CAPTURE_BINDING")
        reservation_id = uuid4()
        deadline = visit.expires_at
        await db.execute(text("""
            INSERT INTO inspection_upload_reservation
                (id, visit_id, assignment_id, generation, target_id, client_capture_id,
                 upload_key, digest, byte_length, deadline)
            VALUES (:id, :visit_id, :assignment_id, :generation, :target_id, :client_capture_id,
                    :upload_key, :digest, :byte_length, :deadline)
        """), params | {"id": reservation_id, "target_id": target_id, "deadline": deadline})
    return InspectionCaptureReservation(
        **request.model_dump(), reservation_id=reservation_id, visit_id=visit.id,
        tenant_id=visit.tenant_id, vendor_id=visit.vendor_id, deadline=deadline,
        replayed=bool(existing),
    )


async def get_inspection_package(
    db: AsyncSession, *, actor: Vendor, visit_id: UUID, owner_client_id: UUID,
    assignment_id: UUID, generation: int,
) -> InspectionPackage:
    visit = await lock_vendor_visit(
        db, tenant_id=actor.tenant_id, vendor_id=actor.vendor_id, visit_id=visit_id,
        owner_client_id=owner_client_id, assignment_id=assignment_id, generation=generation,
    )
    if visit.package_sealed_at is None:
        raise HTTPException(409, "PACKAGE_NOT_SEALED")
    rows = (await db.execute(text("""
        SELECT d.id, d.form_version_id, d.ordinal, d.requirement_id, d.instance_number, f.definition,
               COALESCE((
                   SELECT jsonb_agg(jsonb_build_object(
                       'field_id', t.field_id, 'slot_id', t.slot_id, 'repeat_item_id', t.repeat_item_id, 'required', t.required
                   ) ORDER BY t.field_id, t.slot_id, t.repeat_item_id)
                   FROM inspection_capture_target AS t WHERE t.document_instance_id = d.id
               ), '[]'::jsonb) AS capture_targets
        FROM inspection_document_instance AS d
        JOIN inspection_form_version AS f ON f.id = d.form_version_id
        WHERE d.visit_id = :visit_id ORDER BY d.ordinal
    """), {"visit_id": visit.id})).mappings().all()
    requirements = await package_requirements(db, visit)
    return InspectionPackage(
        visit_id=visit.id, tenant_id=visit.tenant_id, owner_client_id=visit.owner_client_id,
        vendor_id=visit.vendor_id, assignment_id=visit.assignment_id, generation=visit.generation,
        expires_at=visit.expires_at, revision=visit.revision, server_time=await db.scalar(select(func.clock_timestamp())),
        workflow_version_id=visit.workflow_version_id,
        document_requirements=requirements,
        code="PACKAGE_READY" if supports_capture_package(rows, requirements)
        else "PACKAGE_UNSUPPORTED",
        documents=[InspectionPackageDocument(**row) for row in rows],
    )


async def package_requirements(db: AsyncSession, visit: InspectionVisit):
    return (await db.execute(text("""
        SELECT r.id, r.position, r.form_version_id, r.min_instances,
               r.max_instances, r.activation_condition
        FROM inspection_document_requirement AS r
        JOIN inspection_workflow_version AS w ON w.id = r.workflow_version_id
        WHERE w.id = :workflow AND w.published_at IS NOT NULL ORDER BY r.position
    """), {"workflow": visit.workflow_version_id})).mappings().all()


def supports_capture_package(documents, requirements) -> bool:
    if len(documents) != 1 or len(requirements) != 1:
        return False
    document, requirement = documents[0], requirements[0]
    if (
        requirement["min_instances"] != 1 or requirement["max_instances"] != 1
        or requirement["activation_condition"] is not None or document["instance_number"] != 1
        or document["requirement_id"] != requirement["id"]
    ):
        return False
    definition = document["definition"]
    required = definition.get("required_capabilities", [])
    return definition.get("schema_format_version", 1) == 1 and isinstance(required, list) and all(
        capability in ("repeat_items", "photo_slots") for capability in required
    )


async def require_capture_package(db: AsyncSession, visit: InspectionVisit) -> None:
    if visit.package_sealed_at is None:
        raise HTTPException(409, "PACKAGE_NOT_SEALED")
    documents = (await db.execute(text("""
        SELECT d.requirement_id, d.instance_number, f.definition
        FROM inspection_document_instance AS d
        JOIN inspection_form_version AS f ON f.id = d.form_version_id
        WHERE d.visit_id = :visit_id ORDER BY d.ordinal
    """), {"visit_id": visit.id})).mappings().all()
    if not supports_capture_package(documents, await package_requirements(db, visit)):
        raise HTTPException(409, "UNSUPPORTED_VISIT_DOCUMENT_CONFIGURATION")


async def lock_finalization(
    db: AsyncSession, *, actor: Vendor, visit_id: UUID, reservation_id: UUID,
    request: InspectionCaptureFinalize,
):
    visit = await lock_vendor_visit_access(
        db, tenant_id=actor.tenant_id, vendor_id=actor.vendor_id, visit_id=visit_id,
        owner_client_id=request.owner_client_id, assignment_id=request.assignment_id,
        generation=request.generation,
    )
    row = (await db.execute(text("""
        SELECT r.deadline, r.client_capture_id, r.upload_key, r.digest, r.byte_length,
               t.document_instance_id, t.field_id, t.slot_id, t.repeat_item_id,
               c.id AS receipt_id, c.evidence_id, c.key_id, c.signature, c.received_at,
               x.reservation_id IS NOT NULL AS abandoned,
               k.revoked_at AS key_revoked_at
        FROM inspection_upload_reservation AS r
        JOIN inspection_capture_target AS t ON t.id = r.target_id
        LEFT JOIN inspection_capture_receipt AS c ON c.reservation_id = r.id
        LEFT JOIN inspection_upload_tombstone AS x ON x.reservation_id = r.id
        LEFT JOIN device_keys AS k ON k.key_id = c.key_id
        WHERE r.id = :reservation_id AND r.assignment_id = :assignment_id
    """), {"reservation_id": reservation_id, "assignment_id": request.assignment_id})).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, "CAPTURE_RESERVATION_NOT_FOUND")
    if row["abandoned"]:
        raise HTTPException(410, "CAPTURE_RESERVATION_ABANDONED")
    for field in ("client_capture_id", "upload_key", "digest", "byte_length", "document_instance_id",
                  "field_id", "slot_id", "repeat_item_id"):
        if row[field] != getattr(request, field):
            raise HTTPException(409, "IDEMPOTENCY_PAYLOAD_MISMATCH")
    if row["receipt_id"] is not None and (
        row["key_id"] != request.key_id or row["signature"] != request.signature
    ):
        raise HTTPException(409, "IDEMPOTENCY_PAYLOAD_MISMATCH")
    now = await db.scalar(select(func.clock_timestamp()))
    if now > row["deadline"]:
        raise HTTPException(410, "VISIT_EXPIRED")
    if row["receipt_id"] is None:
        await check_open_visit(db, visit)
    return visit, row


def capture_result(request, visit, reservation_id, row, *, replayed):
    reason = "EVIDENCE_KEY_REVOKED" if row["key_revoked_at"] is not None else None
    return InspectionCaptureResult(
        **request.model_dump(exclude={"signature", "key_id"}),
        reservation_id=reservation_id, visit_id=visit.id, tenant_id=visit.tenant_id,
        vendor_id=visit.vendor_id, deadline=row["deadline"], replayed=replayed,
        receipt_id=row["receipt_id"], evidence_id=row["evidence_id"],
        received_at=row["received_at"], eligible=reason is None, eligibility_reason=reason,
    )


async def finalize_inspection_capture(
    db: AsyncSession, *, actor: Vendor, visit_id: UUID, reservation_id: UUID,
    request: InspectionCaptureFinalize, storage: InspectionOriginalStorage,
) -> InspectionCaptureResult:
    scope = dict(actor=actor, visit_id=visit_id, reservation_id=reservation_id, request=request)
    visit, row = await lock_finalization(db, **scope)
    if row["receipt_id"] is not None:
        return capture_result(request, visit, reservation_id, row, replayed=True)

    # End the read-only authorization transaction before storage I/O.
    await db.commit()
    try:
        original = await storage.read_original(reservation_id)
    except HTTPException as error:
        if (error.status_code, error.detail) != (409, "CAPTURE_ORIGINAL_NOT_STORED"):
            raise
        # Another request may have committed and the retention pass may have
        # removed staged bytes while this request was outside its locks.
        visit, row = await lock_finalization(db, **scope)
        if row["receipt_id"] is not None:
            return capture_result(request, visit, reservation_id, row, replayed=True)
        raise
    visit, row = await lock_finalization(db, **scope)
    if row["receipt_id"] is not None:
        return capture_result(request, visit, reservation_id, row, replayed=True)

    received_at = getattr(original, "received_at", None)
    if not isinstance(received_at, datetime) or received_at.utcoffset() is None:
        raise HTTPException(503, "INSPECTION_STORAGE_RECEIPT_INVALID")
    verified = await verify_inspection_original(
        db, visit=visit, key_id=request.key_id, received_at=received_at,
        original=original.content, deadline=row["deadline"],
        expected_digest=row["digest"], expected_length=row["byte_length"],
        signature_b64=request.signature,
    )
    evidence = Evidence(
        evidence_id=uuid5(reservation_id, "trustcapture.gate1.evidence.v1"), tenant_id=visit.tenant_id, vendor_id=visit.vendor_id,
        evidence_type="photo", category="inspection", file_key=original.object_key,
        file_size_bytes=verified.byte_length, file_hash=verified.digest,
        signing_key_id=verified.key_id, signing_key_fingerprint=verified.key_fingerprint,
        device_signature=request.signature, signature_outcome="verified",
    )
    db.add(evidence)
    await db.flush()
    receipt_id = uuid4()
    await db.execute(text("""
        INSERT INTO inspection_capture_receipt
            (id, reservation_id, evidence_id, key_id, signature, received_at, verification_method, storage_backend_id, storage_reference)
        VALUES (:id, :reservation_id, :evidence_id, :key_id, :signature, :received_at, :method, :storage_backend, :storage_reference)
    """), {
        "id": receipt_id, "reservation_id": reservation_id, "evidence_id": evidence.evidence_id,
        "key_id": verified.key_id, "signature": request.signature, "received_at": verified.received_at,
        "method": verified.method, "storage_backend": getattr(original, "backend_id", "legacy"),
        "storage_reference": original.object_key,
    })
    return capture_result(request, visit, reservation_id, dict(
        receipt_id=receipt_id, evidence_id=evidence.evidence_id, received_at=verified.received_at,
        deadline=row["deadline"], key_revoked_at=None,
    ), replayed=False)


async def resolve_inspection_upload(
    db: AsyncSession, *, actor: Vendor, visit_id: UUID, owner_client_id: UUID,
    assignment_id: UUID, generation: int, reservation_id: UUID,
):
    visit = await lock_vendor_visit(
        db, tenant_id=actor.tenant_id, vendor_id=actor.vendor_id, visit_id=visit_id,
        owner_client_id=owner_client_id, assignment_id=assignment_id, generation=generation,
    )
    reservation = (await db.execute(text("""
        SELECT r.digest, r.byte_length, r.deadline, t.reservation_id IS NOT NULL AS abandoned
        FROM inspection_upload_reservation AS r
        LEFT JOIN inspection_upload_tombstone AS t ON t.reservation_id = r.id
        WHERE r.id = :id AND r.assignment_id = :assignment AND r.visit_id = :visit
    """), {"id": reservation_id, "assignment": visit.assignment_id, "visit": visit.id})).mappings().one_or_none()
    if reservation is None:
        raise HTTPException(404, "CAPTURE_RESERVATION_NOT_FOUND")
    if reservation["abandoned"]:
        raise HTTPException(410, "CAPTURE_RESERVATION_ABANDONED")
    if await db.scalar(select(func.clock_timestamp())) > reservation["deadline"]:
        raise HTTPException(410, "VISIT_EXPIRED")
    return reservation


async def clean_expired_inspection_original(
    db: AsyncSession, *, reservation_id: UUID, storage: InspectionOriginalStorage,
) -> bool:
    """Internal maintenance operation. Fence the reservation before storage deletion."""
    visit_id = await db.scalar(text("""
        SELECT visit_id FROM inspection_upload_reservation WHERE id = :id
    """), {"id": reservation_id})
    if visit_id is None:
        return False
    await db.execute(select(InspectionVisit.id).where(InspectionVisit.id == visit_id).with_for_update())
    claimed = await db.scalar(text("""
        INSERT INTO inspection_upload_tombstone (reservation_id)
        SELECT r.id FROM inspection_upload_reservation AS r
        WHERE r.id = :id AND r.deadline < clock_timestamp()
          AND NOT EXISTS (SELECT 1 FROM inspection_capture_receipt WHERE reservation_id = r.id)
        ON CONFLICT (reservation_id) DO NOTHING
        RETURNING reservation_id
    """), {"id": reservation_id})
    if claimed is None:
        claimed = await db.scalar(text("""
            SELECT reservation_id FROM inspection_upload_tombstone WHERE reservation_id = :id
        """), {"id": reservation_id})
    await db.commit()
    if claimed is None:
        return False
    await storage.abandon_original(reservation_id)
    return True


async def resolve_inspection_original(
    db: AsyncSession, *, actor: Vendor, visit_id: UUID, owner_client_id: UUID,
    assignment_id: UUID, generation: int, evidence_id: UUID,
):
    visit = await lock_vendor_visit_access(
        db, tenant_id=actor.tenant_id, vendor_id=actor.vendor_id, visit_id=visit_id,
        owner_client_id=owner_client_id, assignment_id=assignment_id, generation=generation,
    )
    if visit.submitted_at is None:
        await check_open_visit(db, visit)
    receipt = (await db.execute(text("""
        SELECT c.storage_backend_id, c.storage_reference, r.byte_length, r.digest
        FROM inspection_capture_receipt AS c
        JOIN inspection_upload_reservation AS r ON r.id = c.reservation_id
        JOIN evidence AS e ON e.evidence_id = c.evidence_id
        WHERE c.evidence_id = :evidence AND r.visit_id = :visit AND r.assignment_id = :assignment
          AND r.generation = :generation AND e.tenant_id = :tenant AND e.vendor_id = :vendor
    """), dict(evidence=evidence_id, visit=visit.id, assignment=visit.assignment_id,
               generation=visit.generation, tenant=visit.tenant_id, vendor=visit.vendor_id))).mappings().one_or_none()
    if receipt is None:
        raise HTTPException(404, "INSPECTION_EVIDENCE_NOT_FOUND")
    if receipt["storage_backend_id"] == "legacy" or receipt["storage_reference"] is None:
        raise HTTPException(503, "INSPECTION_STORAGE_UNAVAILABLE")
    return receipt
