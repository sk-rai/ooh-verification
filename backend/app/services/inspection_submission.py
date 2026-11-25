"""Accept and replay a single pinned Gate 1 document atomically."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.inspection_authz import check_open_visit, lock_vendor_visit_access, require_receipt_key
from app.models.inspection_visit import InspectionVisit
from app.models.vendor import Vendor
from app.schemas.inspection_submission import (
    InspectionDocumentAnswer, InspectionSubmitRequest, InspectionSubmitResult,
)
from app.services.inspection_capture import require_capture_package


def canonical_json(value) -> str:
    """RFC 8785 on the Gate 1 domain: decimals are strings, integers are JS-safe."""
    def ordered(item):
        if isinstance(item, dict):
            return {key: ordered(item[key]) for key in sorted(item, key=lambda key: key.encode("utf-16-be"))}
        if isinstance(item, list):
            return [ordered(value) for value in item]
        if type(item) is int and abs(item) <= 9007199254740991:
            return item
        if item is None or type(item) in (str, bool):
            return item
        raise ValueError("value outside Gate 1 canonical profile")

    try:
        encoded = json.dumps(ordered(value), separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        encoded.encode("utf-8")  # Reject invalid Unicode even in string values.
        return encoded
    except (ValueError, TypeError, RecursionError):
        raise HTTPException(422, "INVALID_DOCUMENT_ANSWERS") from None


def utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def valid_decimal(value, rule: dict) -> bool:
    if not isinstance(value, dict) or set(value) != {"value", "scale", "unit"}:
        return False
    scale = rule.get("scale")
    unit = rule.get("unit")
    if type(scale) is not int or not 0 <= scale <= 18 or not isinstance(unit, str) or not unit:
        raise HTTPException(409, "UNSUPPORTED_VISIT_DOCUMENT_CONFIGURATION")
    if type(value["scale"]) is not int or value["scale"] != scale or value["unit"] != unit:
        return False
    fraction = rf"\.[0-9]{{{scale}}}" if scale else ""
    decimal = value["value"]
    return (isinstance(decimal, str) and len(decimal) <= 80
            and re.fullmatch(r"-?(?:0|[1-9][0-9]*)" + fraction, decimal) is not None)


def digest_of(canonical: str) -> str:
    return sha256(canonical.encode("utf-8")).hexdigest()


def validate_repeat_answers(document: InspectionDocumentAnswer, definition: dict) -> None:
    expected = definition.get("repeat_items", [])
    actual = [str(item.repeat_item_id) for item in document.repeat_items]
    if actual != expected or len(set(actual)) != len(actual):
        raise HTTPException(422, "INVALID_REPEAT_ITEM_SET")
    fields = definition.get("repeat_fields", {})
    if not isinstance(fields, dict):
        raise HTTPException(409, "UNSUPPORTED_VISIT_DOCUMENT_CONFIGURATION")
    types = {"text": str, "number": dict, "boolean": bool}
    for field in fields.values():
        if not isinstance(field, dict) or field.get("type") not in types:
            raise HTTPException(409, "UNSUPPORTED_VISIT_DOCUMENT_CONFIGURATION")
    for item in document.repeat_items:
        if set(item.answers) - set(fields):
            raise HTTPException(422, "INVALID_DOCUMENT_ANSWERS")
        for name, rule in fields.items():
            if name not in item.answers:
                if rule.get("required"):
                    raise HTTPException(422, "INVALID_DOCUMENT_ANSWERS")
            elif type(item.answers[name]) is not types[rule["type"]] or (
                rule["type"] == "number" and not valid_decimal(item.answers[name], rule)
            ):
                raise HTTPException(422, "INVALID_DOCUMENT_ANSWERS")


async def freeze_evidence(
    db: AsyncSession, *, visit: InspectionVisit, document: InspectionDocumentAnswer,
) -> list[dict]:
    rows = (await db.execute(text("""
        SELECT field_id, slot_id, repeat_item_id, required
        FROM inspection_capture_target WHERE document_instance_id = :document
    """), {"document": document.document_instance_id})).mappings().all()
    wanted = {(r["field_id"], r["slot_id"], r["repeat_item_id"]): r["required"] for r in rows}
    seen = set()
    evidence_ids = set()
    result = []
    for answer in document.evidence:
        target = (answer.field_id, answer.slot_id, answer.repeat_item_id)
        if target not in wanted or target in seen or answer.evidence_id in evidence_ids:
            raise HTTPException(422, "INVALID_CAPTURE_BINDING")
        row = (await db.execute(text("""
            SELECT c.id AS receipt_id, c.key_id, c.received_at, c.verification_method, r.digest
            FROM inspection_capture_receipt AS c
            JOIN inspection_upload_reservation AS r ON r.id = c.reservation_id
            JOIN inspection_capture_target AS t ON t.id = r.target_id
            JOIN evidence AS e ON e.evidence_id = c.evidence_id
            WHERE c.evidence_id = :evidence AND r.visit_id = :visit AND r.assignment_id = :assignment
              AND r.generation = :generation AND t.document_instance_id = :document
              AND t.field_id = :field AND t.slot_id = :slot
              AND t.repeat_item_id IS NOT DISTINCT FROM CAST(:item AS uuid)
              AND e.tenant_id = :tenant AND e.vendor_id = :vendor AND e.file_hash = r.digest
              AND c.received_at <= r.deadline
        """), dict(evidence=answer.evidence_id, visit=visit.id, assignment=visit.assignment_id,
                   generation=visit.generation, document=document.document_instance_id,
                   field=answer.field_id, slot=answer.slot_id, item=answer.repeat_item_id,
                   tenant=visit.tenant_id, vendor=visit.vendor_id))).mappings().one_or_none()
        if row is None:
            raise HTTPException(422, "INVALID_CAPTURE_BINDING")
        key = await require_receipt_key(db, visit=visit, key_id=row["key_id"], received_at=row["received_at"])
        result.append(answer.model_dump(mode="json") | {
            "receipt_id": str(row["receipt_id"]), "digest": row["digest"],
            "verification_method": row["verification_method"], "received_at": utc_timestamp(row["received_at"]),
            "key_id": str(key.key_id), "key_fingerprint": key.key_fingerprint,
        })
        seen.add(target)
        evidence_ids.add(answer.evidence_id)
    if any(required and target not in seen for target, required in wanted.items()):
        raise HTTPException(422, "REQUIRED_EVIDENCE_MISSING")
    return sorted(result, key=lambda value: (value["field_id"], value["slot_id"], value["repeat_item_id"] or ""))


async def submit_inspection(
    db: AsyncSession, *, actor: Vendor, visit_id: UUID, request: InspectionSubmitRequest,
) -> InspectionSubmitResult:
    visit = await lock_vendor_visit_access(
        db, tenant_id=actor.tenant_id, vendor_id=actor.vendor_id, visit_id=visit_id,
        owner_client_id=request.owner_client_id, assignment_id=request.assignment_id,
        generation=request.generation,
    )
    request_digest = digest_of(canonical_json(request.model_dump(mode="json", exclude={"submit_key"})))
    existing = (await db.execute(text("""
        SELECT id, request_digest, manifest, manifest_digest, submitted_at, accepted_revision
        FROM inspection_visit_submission
        WHERE visit_id = :visit AND assignment_id = :assignment AND submit_key = :key AND sealed
    """), {"visit": visit.id, "assignment": visit.assignment_id, "key": request.submit_key})).mappings().one_or_none()
    if existing is not None:
        if existing["request_digest"] != request_digest:
            raise HTTPException(409, "IDEMPOTENCY_PAYLOAD_MISMATCH")
        return InspectionSubmitResult(
            submission_id=existing["id"], visit_id=visit.id, assignment_id=visit.assignment_id,
            generation=visit.generation, submitted_at=existing["submitted_at"],
            accepted_revision=existing["accepted_revision"],
            manifest_digest=existing["manifest_digest"], documents=json.loads(existing["manifest"])["documents"],
            replayed=True,
        )

    await check_open_visit(db, visit)
    if request.expected_revision != visit.revision:
        raise HTTPException(409, "VISIT_REVISION_CONFLICT")
    await require_capture_package(db, visit)
    pinned = (await db.execute(text("""
        SELECT d.id, d.form_version_id, f.definition
        FROM inspection_document_instance AS d
        JOIN inspection_form_version AS f ON f.id = d.form_version_id
        WHERE d.visit_id = :visit
    """), {"visit": visit.id})).mappings().one()
    if [doc.document_instance_id for doc in request.documents] != [pinned["id"]]:
        raise HTTPException(422, "INVALID_DOCUMENT_INSTANCE_SET")
    document = request.documents[0]
    validate_repeat_answers(document, pinned["definition"])
    evidence = await freeze_evidence(db, visit=visit, document=document)
    revision, submission = uuid4(), uuid4()
    accepted_at = await db.scalar(select(func.clock_timestamp()))
    if accepted_at > visit.expires_at:
        raise HTTPException(410, "VISIT_EXPIRED")
    accepted_revision = visit.revision + 1
    content = canonical_json({
        "version": 1, "document_instance_id": str(pinned["id"]),
        "form_version_id": str(pinned["form_version_id"]), "evidence": evidence,
        "repeat_items": [item.model_dump(mode="json") for item in document.repeat_items],
    })
    documents = [{
        "document_instance_id": str(pinned["id"]), "revision_id": str(revision), "digest": digest_of(content),
    }]
    manifest = canonical_json({
        "version": 1, "visit_id": str(visit.id), "assignment_id": str(visit.assignment_id),
        "generation": visit.generation, "workflow_version_id": str(visit.workflow_version_id),
        "submitted_at": utc_timestamp(accepted_at), "accepted_revision": accepted_revision,
        "documents": documents,
    })
    manifest_digest = digest_of(manifest)
    await db.execute(text("""
        INSERT INTO inspection_document_revision (id, visit_id, document_instance_id, content, digest)
        VALUES (:id, :visit, :document, :content, :digest)
    """), dict(id=revision, visit=visit.id, document=pinned["id"], content=content, digest=documents[0]["digest"]))
    await db.execute(text("""
        INSERT INTO inspection_visit_submission (id, visit_id, assignment_id, generation, submit_key,
            request_digest, manifest, manifest_digest, submitted_at, accepted_revision)
        VALUES (:id, :visit, :assignment, :generation, :key, :request_digest,
                :manifest, :digest, :submitted_at, :accepted_revision)
    """), dict(id=submission, visit=visit.id, assignment=visit.assignment_id, generation=visit.generation,
               key=request.submit_key, request_digest=request_digest, manifest=manifest,
               digest=manifest_digest, submitted_at=accepted_at, accepted_revision=accepted_revision))
    await db.execute(text("""
        INSERT INTO inspection_submission_document (submission_id, visit_id, document_instance_id,
                                                     revision_id, ordinal)
        VALUES (:submission, :visit, :document, :revision, 1)
    """), dict(submission=submission, visit=visit.id, document=pinned["id"], revision=revision))
    stored_documents = (await db.execute(text("""
        SELECT m.document_instance_id, m.revision_id, d.digest
        FROM inspection_submission_document AS m
        JOIN inspection_document_revision AS d ON d.id = m.revision_id
        WHERE m.submission_id = :submission ORDER BY m.ordinal
    """), {"submission": submission})).mappings().all()
    if [
        {"document_instance_id": str(row["document_instance_id"]),
         "revision_id": str(row["revision_id"]), "digest": row["digest"]}
        for row in stored_documents
    ] != documents:
        raise RuntimeError("Inspection manifest differs from stored membership")
    await db.execute(text("""
        UPDATE inspection_visit_submission SET sealed = true WHERE id = :submission
    """), {"submission": submission})
    visit.submitted_at = accepted_at
    visit.revision = accepted_revision
    await db.flush()
    return InspectionSubmitResult(
        submission_id=submission, visit_id=visit.id, assignment_id=visit.assignment_id,
        generation=visit.generation, submitted_at=accepted_at, manifest_digest=manifest_digest,
        documents=documents, replayed=False, accepted_revision=accepted_revision,
    )
