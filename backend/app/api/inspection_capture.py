"""Gate 1 capture reservation routes."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_vendor
from app.models.vendor import Vendor
from app.schemas.inspection_capture import (
    InspectionCaptureFinalize, InspectionCaptureRequest, InspectionCaptureReservation,
    InspectionCaptureResult, InspectionOriginalStored, InspectionPackage,
)
from app.services.inspection_capture import (
    finalize_inspection_capture, get_inspection_package, reserve_inspection_upload,
    resolve_inspection_original, resolve_inspection_upload,
)
from app.schemas.inspection_submission import InspectionSubmitRequest, InspectionSubmitResult
from app.services.inspection_submission import submit_inspection
from app.services.inspection_original_storage import MAX_ORIGINAL_BYTES, InspectionOriginalStorage, get_inspection_original_storage


router = APIRouter(prefix="/api/inspection-visits", tags=["inspection-visits"])


@router.post("/{visit_id}/capture-reservations", response_model=InspectionCaptureReservation, status_code=201)
async def reserve_capture(
    visit_id: UUID, data: InspectionCaptureRequest, response: Response,
    vendor: Vendor = Depends(get_current_vendor), db: AsyncSession = Depends(get_db),
):
    result = await reserve_inspection_upload(db, actor=vendor, visit_id=visit_id, request=data)
    await db.commit()
    if result.replayed:
        response.status_code = 200
    return result


@router.get("/{visit_id}/package", response_model=InspectionPackage)
async def read_package(
    visit_id: UUID, owner_client_id: UUID, assignment_id: UUID, generation: int = Query(gt=0),
    vendor: Vendor = Depends(get_current_vendor), db: AsyncSession = Depends(get_db),
):
    return await get_inspection_package(
        db, actor=vendor, visit_id=visit_id, owner_client_id=owner_client_id,
        assignment_id=assignment_id, generation=generation,
    )


@router.post("/{visit_id}/capture-reservations/{reservation_id}/finalize",
             response_model=InspectionCaptureResult, status_code=201)
async def finalize_capture(
    visit_id: UUID, reservation_id: UUID, data: InspectionCaptureFinalize, response: Response,
    vendor: Vendor = Depends(get_current_vendor), db: AsyncSession = Depends(get_db),
    storage: InspectionOriginalStorage = Depends(get_inspection_original_storage),
):
    result = await finalize_inspection_capture(
        db, actor=vendor, visit_id=visit_id, reservation_id=reservation_id, request=data, storage=storage,
    )
    await db.commit()
    if result.replayed:
        response.status_code = 200
    return result


@router.post("/{visit_id}/submit", response_model=InspectionSubmitResult, status_code=201)
async def submit_visit(
    visit_id: UUID, data: InspectionSubmitRequest,
    vendor: Vendor = Depends(get_current_vendor), db: AsyncSession = Depends(get_db),
):
    result = await submit_inspection(db, actor=vendor, visit_id=visit_id, request=data)
    await db.commit()
    return result


@router.put("/{visit_id}/capture-reservations/{reservation_id}/original", response_model=InspectionOriginalStored)
async def store_capture_original(
    visit_id: UUID, reservation_id: UUID, owner_client_id: UUID, assignment_id: UUID,
    request: Request, generation: int = Query(gt=0),
    vendor: Vendor = Depends(get_current_vendor), db: AsyncSession = Depends(get_db),
    storage: InspectionOriginalStorage = Depends(get_inspection_original_storage),
):
    reservation = await resolve_inspection_upload(
        db, actor=vendor, visit_id=visit_id, owner_client_id=owner_client_id, assignment_id=assignment_id,
        generation=generation, reservation_id=reservation_id,
    )
    await db.commit()
    max_bytes = min(reservation["byte_length"], getattr(storage, "max_bytes", MAX_ORIGINAL_BYTES))
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > max_bytes:
            raise HTTPException(413, "CAPTURE_ORIGINAL_TOO_LARGE")
        content.extend(chunk)
    reservation = await resolve_inspection_upload(
        db, actor=vendor, visit_id=visit_id, owner_client_id=owner_client_id, assignment_id=assignment_id,
        generation=generation, reservation_id=reservation_id,
    )
    await db.commit()
    stored = await storage.store_original(
        reservation_id, bytes(content), expected_digest=reservation["digest"],
        expected_length=reservation["byte_length"], deadline=reservation["deadline"],
    )
    return InspectionOriginalStored(reservation_id=reservation_id, received_at=stored.received_at)


@router.get("/{visit_id}/evidence/{evidence_id}/original")
async def read_capture_original(
    visit_id: UUID, evidence_id: UUID, owner_client_id: UUID, assignment_id: UUID,
    generation: int = Query(gt=0), vendor: Vendor = Depends(get_current_vendor),
    db: AsyncSession = Depends(get_db),
    storage: InspectionOriginalStorage = Depends(get_inspection_original_storage),
):
    scope = dict(actor=vendor, visit_id=visit_id, owner_client_id=owner_client_id,
                 assignment_id=assignment_id, generation=generation, evidence_id=evidence_id)
    receipt = await resolve_inspection_original(db, **scope)
    await db.commit()
    content = await storage.read_finalized(
        receipt["storage_backend_id"], receipt["storage_reference"],
        length=receipt["byte_length"], digest=receipt["digest"],
    )
    await resolve_inspection_original(db, **scope)
    return Response(content=content, media_type="application/octet-stream", headers={
        "Cache-Control": "private, no-store",
        "Content-Disposition": "attachment",
        "X-Content-Type-Options": "nosniff",
    })
