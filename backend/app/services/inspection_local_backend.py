"""Permanent local originals using the existing write-once filesystem adapter."""
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from fastapi import HTTPException

from app.services.inspection_original_storage import LocalInspectionStorage


class LocalPermanentOriginalStore:

    def __init__(self, root):
        root = root.resolve()
        self.backend_id = sha256(f"filesystem:v1:{root}".encode()).hexdigest()
        self.storage = LocalInspectionStorage(root)

    async def create_if_absent(self, reservation_id: UUID, content: bytes) -> None:
        await self.storage.store_original(
            reservation_id, content, expected_digest=sha256(content).hexdigest(),
            expected_length=len(content), deadline=datetime.max.replace(tzinfo=timezone.utc),
        )

    async def retrieve(self, reservation_id: UUID, *, limit: int) -> bytes:
        original = await self.storage.read_original(reservation_id)
        if len(original.content) > limit:
            raise HTTPException(409, "INSPECTION_ORIGINAL_CONFLICT")
        return original.content

    async def delete_abandoned(self, reservation_id: UUID) -> None:
        await self.storage.abandon_original(reservation_id)
