"""Gate 1 single-document submission contract."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class InspectionEvidenceAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: str = Field(min_length=1, max_length=100)
    slot_id: str = Field(min_length=1, max_length=100)
    repeat_item_id: UUID | None
    evidence_id: UUID


class InspectionRepeatAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repeat_item_id: UUID
    answers: dict[str, JsonValue]


class InspectionDocumentAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_instance_id: UUID
    repeat_items: list[InspectionRepeatAnswer] = Field(max_length=100)
    evidence: list[InspectionEvidenceAnswer] = Field(max_length=100)


class InspectionSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_client_id: UUID
    assignment_id: UUID
    generation: int = Field(gt=0, le=9223372036854775807)
    expected_revision: int = Field(ge=0)
    submit_key: str = Field(min_length=1, max_length=128)
    documents: list[InspectionDocumentAnswer] = Field(max_length=10)


class InspectionRevisionReference(BaseModel):
    revision_id: UUID
    document_instance_id: UUID
    digest: str


class InspectionSubmitResult(BaseModel):
    code: str = "VISIT_SUBMITTED"
    submission_id: UUID
    visit_id: UUID
    assignment_id: UUID
    generation: int
    accepted_revision: int
    submitted_at: datetime
    manifest_digest: str
    documents: list[InspectionRevisionReference]
    replayed: bool
