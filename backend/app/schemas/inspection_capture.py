"""Wire contracts for pinned inspection packages and capture reservations."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class InspectionCaptureRequest(BaseModel):
    owner_client_id: UUID
    assignment_id: UUID
    generation: int = Field(gt=0, le=9223372036854775807)
    document_instance_id: UUID
    field_id: str = Field(min_length=1, max_length=100)
    slot_id: str = Field(min_length=1, max_length=100)
    repeat_item_id: UUID | None = None
    client_capture_id: UUID
    upload_key: str = Field(min_length=1, max_length=128)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(gt=0, le=10485760)


class InspectionCaptureReservation(InspectionCaptureRequest):
    reservation_id: UUID
    visit_id: UUID
    tenant_id: UUID
    vendor_id: str
    deadline: datetime
    replayed: bool
    code: str = "CAPTURE_RESERVED"

class InspectionCaptureTarget(BaseModel):
    field_id: str
    slot_id: str
    repeat_item_id: UUID | None
    required: bool


class InspectionPackageDocument(BaseModel):
    id: UUID
    form_version_id: UUID
    ordinal: int
    requirement_id: UUID
    instance_number: int
    definition: dict
    capture_targets: list[InspectionCaptureTarget]


class InspectionDocumentRequirement(BaseModel):
    id: UUID
    position: int
    form_version_id: UUID
    min_instances: int
    max_instances: int
    activation_condition: dict | None


class InspectionPackage(BaseModel):
    visit_id: UUID
    tenant_id: UUID
    owner_client_id: UUID
    vendor_id: str
    assignment_id: UUID
    generation: int
    expires_at: datetime
    server_time: datetime
    revision: int
    code: str
    workflow_version_id: UUID
    document_requirements: list[InspectionDocumentRequirement]
    documents: list[InspectionPackageDocument]

class InspectionCaptureFinalize(InspectionCaptureRequest):
    key_id: UUID
    signature: str = Field(min_length=1, max_length=256)


class InspectionCaptureResult(InspectionCaptureReservation):
    receipt_id: UUID
    evidence_id: UUID
    received_at: datetime
    eligible: bool
    eligibility_reason: str | None = None
    code: str = "CAPTURE_ACCEPTED"

class InspectionOriginalStored(BaseModel):
    code: str = "CAPTURE_ORIGINAL_STORED"
    reservation_id: UUID
    received_at: datetime
