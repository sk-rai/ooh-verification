"""Provider-independent durable staging and permanent original storage."""
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from fastapi import HTTPException

from app.services.inspection_original_storage import StoredInspectionOriginal


@dataclass(frozen=True)
class StagedOriginal:
    backend_id: str
    content: bytes
    received_at: datetime


class OriginalStaging(Protocol):
    async def accept(self, reservation_id: UUID, content: bytes, backend_id: str) -> StagedOriginal: ...
    async def read(self, reservation_id: UUID) -> StagedOriginal: ...
    async def backend_for(self, reservation_id: UUID) -> str | None: ...
    async def discard_abandoned(self, reservation_id: UUID) -> None: ...
    async def expired_unfinalized(self, *, after: UUID | None, limit: int) -> list[UUID]: ...
    async def purge_finalized(self, *, older_than_seconds: int, limit: int = 100) -> int: ...


class PermanentOriginalStore(Protocol):
    backend_id: str

    async def create_if_absent(self, reservation_id: UUID, content: bytes) -> None: ...
    async def retrieve(self, reservation_id: UUID, *, limit: int) -> bytes: ...
    async def delete_abandoned(self, reservation_id: UUID) -> None: ...


class StagedInspectionStorage:
    def __init__(self, staging: OriginalStaging, stores: dict[str, PermanentOriginalStore],
                 active_backend: str, *, max_bytes: int):
        if active_backend not in stores or any(key != store.backend_id for key, store in stores.items()):
            raise ValueError("Invalid inspection storage registry")
        self.staging = staging
        self.stores = dict(stores)
        self.active_backend = active_backend
        self.max_bytes = max_bytes

    def backend(self, backend_id: str) -> PermanentOriginalStore:
        if backend_id not in self.stores:
            raise HTTPException(503, "INSPECTION_STORAGE_UNAVAILABLE")
        return self.stores[backend_id]

    async def _publish(self, reservation_id: UUID, staged: StagedOriginal) -> StoredInspectionOriginal:
        backend = self.backend(staged.backend_id)
        try:
            stored = await backend.retrieve(reservation_id, limit=len(staged.content))
        except HTTPException as missing:
            if missing.detail != "CAPTURE_ORIGINAL_NOT_STORED":
                raise
            try:
                await backend.create_if_absent(reservation_id, staged.content)
            except HTTPException as failure:
                if failure.status_code != 503:
                    raise
                # The provider can commit before a response is lost.
                try:
                    stored = await backend.retrieve(reservation_id, limit=len(staged.content))
                except HTTPException:
                    raise failure from None
            else:
                stored = await backend.retrieve(reservation_id, limit=len(staged.content))
        if len(stored) != len(staged.content) or sha256(stored).digest() != sha256(staged.content).digest():
            raise HTTPException(409, "INSPECTION_ORIGINAL_CONFLICT")
        return StoredInspectionOriginal(str(reservation_id), stored, staged.received_at, staged.backend_id)

    async def store_original(self, reservation_id: UUID, content: bytes, *, expected_digest: str,
                             expected_length: int, deadline: datetime) -> StoredInspectionOriginal:
        if len(content) > self.max_bytes:
            raise HTTPException(413, "CAPTURE_ORIGINAL_TOO_LARGE")
        if not content or len(content) != expected_length or sha256(content).hexdigest() != expected_digest:
            raise HTTPException(422, "CAPTURE_CONTENT_MISMATCH")
        staged = await self.staging.accept(reservation_id, content, self.active_backend)
        return await self._publish(reservation_id, staged)

    async def read_original(self, reservation_id: UUID) -> StoredInspectionOriginal:
        staged = await self.staging.read(reservation_id)
        return await self._publish(reservation_id, staged)

    async def read_finalized(self, backend_id: str, reference: str, *, length: int, digest: str) -> bytes:
        content = await self.backend(backend_id).retrieve(UUID(reference), limit=length)
        if len(content) != length or sha256(content).hexdigest() != digest:
            raise HTTPException(503, "INSPECTION_STORAGE_CORRUPT")
        return content

    async def abandon_original(self, reservation_id: UUID) -> None:
        # The durable backend pin survives byte purging so later sweeps can
        # find uploads that finished after an earlier deletion.
        backend_id = await self.staging.backend_for(reservation_id)
        if backend_id is not None:
            await self.backend(backend_id).delete_abandoned(reservation_id)
            await self.staging.discard_abandoned(reservation_id)
