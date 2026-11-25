"""PostgreSQL implementation of bounded Gate 1 original staging."""
from hashlib import sha256
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text

from app.core.inspection_authz import lock_vendor_visit

from app.services.inspection_storage_backends import StagedOriginal


class PostgresOriginalStaging:
    def __init__(self, sessions, *, quota_bytes: int):
        if quota_bytes < 1:
            raise ValueError("Staging quota must be positive")
        self.sessions = sessions
        self.quota_bytes = quota_bytes

    async def accept(self, reservation_id: UUID, content: bytes, backend_id: str) -> StagedOriginal:
        params = {"id": reservation_id}
        async with self.sessions.begin() as db:
            # No external I/O while holding this lock. Cleanup and finalization
            # serialize through the same visit row.
            row = (await db.execute(text("""
                SELECT r.deadline, r.digest, r.byte_length, r.visit_id, r.assignment_id, r.generation,
                       v.tenant_id, v.owner_client_id, a.vendor_id
                FROM inspection_upload_reservation r
                JOIN inspection_visit v ON v.id = r.visit_id
                JOIN inspection_assignment a ON a.id = r.assignment_id
                WHERE r.id = :id
            """), params)).mappings().one_or_none()
            if row is None:
                raise HTTPException(404, "CAPTURE_RESERVATION_NOT_FOUND")
            if await db.scalar(text("""
                SELECT 1 FROM inspection_upload_tombstone WHERE reservation_id = :id
            """), params):
                raise HTTPException(410, "CAPTURE_RESERVATION_ABANDONED")
            await lock_vendor_visit(
                db, tenant_id=row["tenant_id"], owner_client_id=row["owner_client_id"],
                vendor_id=row["vendor_id"], visit_id=row["visit_id"], assignment_id=row["assignment_id"],
                generation=row["generation"],
            )
            if await db.scalar(text("""
                SELECT 1 FROM inspection_upload_tombstone WHERE reservation_id = :id
            """), params):
                raise HTTPException(410, "CAPTURE_RESERVATION_ABANDONED")
            if len(content) != row["byte_length"] or sha256(content).hexdigest() != row["digest"]:
                raise HTTPException(422, "CAPTURE_CONTENT_MISMATCH")
            staged = await self._read(db, reservation_id)
            if staged is not None:
                return staged
            if await db.scalar(text("""
                SELECT 1 FROM inspection_capture_receipt WHERE reservation_id = :id
            """), params):
                raise HTTPException(409, "CAPTURE_ALREADY_FINALIZED")
            # Serialize quota admission, including concurrent uploads on different visits.
            await db.execute(text("SELECT pg_advisory_xact_lock(61927301842)"))
            used = await db.scalar(text("SELECT COALESCE(sum(octet_length(content)), 0) FROM inspection_original_staging"))
            if used + len(content) > self.quota_bytes:
                raise HTTPException(503, "INSPECTION_STAGING_QUOTA_EXCEEDED")
            # Deadline is evaluated at locked admission, after complete bytes and quota
            # are checked. The timestamp is usable only if this transaction commits.
            received_at = await db.scalar(text("SELECT clock_timestamp()"))
            if received_at > row["deadline"]:
                raise HTTPException(410, "VISIT_EXPIRED")
            await db.execute(text("""
                INSERT INTO inspection_original_staging (reservation_id, content, backend_id, received_at)
                VALUES (:id, :content, :backend_id, :received_at)
            """), params | dict(content=content, backend_id=backend_id, received_at=received_at))
            return StagedOriginal(backend_id, content, received_at)

    async def _read(self, db, reservation_id: UUID) -> StagedOriginal | None:
        row = (await db.execute(text("""
            SELECT backend_id, content, received_at FROM inspection_original_staging
            WHERE reservation_id = :id AND content IS NOT NULL
        """), {"id": reservation_id})).mappings().one_or_none()
        return StagedOriginal(**row) if row is not None else None

    async def read(self, reservation_id: UUID) -> StagedOriginal:
        async with self.sessions() as db:
            staged = await self._read(db, reservation_id)
        if staged is None:
            raise HTTPException(409, "CAPTURE_ORIGINAL_NOT_STORED")
        return staged

    async def backend_for(self, reservation_id: UUID) -> str | None:
        async with self.sessions() as db:
            return await db.scalar(text("""
                SELECT backend_id FROM inspection_original_staging WHERE reservation_id = :id
            """), {"id": reservation_id})

    async def discard_abandoned(self, reservation_id: UUID) -> None:
        async with self.sessions.begin() as db:
            await db.execute(text("""
                UPDATE inspection_original_staging s SET content = NULL
                WHERE s.reservation_id = :id AND s.content IS NOT NULL
                AND EXISTS (SELECT 1 FROM inspection_upload_tombstone t WHERE t.reservation_id = s.reservation_id)
            """), {"id": reservation_id})

    async def purge_finalized(self, *, older_than_seconds: int, limit: int = 100) -> int:
        if older_than_seconds < 0 or limit < 1:
            raise ValueError("Invalid staging retention limits")
        async with self.sessions.begin() as db:
            result = await db.execute(text("""
                UPDATE inspection_original_staging SET content = NULL WHERE reservation_id IN (
                    SELECT s.reservation_id FROM inspection_original_staging s
                    JOIN inspection_capture_receipt r ON r.reservation_id = s.reservation_id
                    WHERE s.content IS NOT NULL AND r.received_at <= clock_timestamp() - make_interval(secs => :age)
                    ORDER BY r.received_at LIMIT :limit FOR UPDATE OF s SKIP LOCKED
                )
            """), {"age": older_than_seconds, "limit": limit})
            return result.rowcount

    async def expired_unfinalized(self, *, after: UUID | None, limit: int) -> list[UUID]:
        async with self.sessions() as db:
            return list((await db.scalars(text("""
                SELECT s.reservation_id
                FROM inspection_original_staging s
                JOIN inspection_upload_reservation r ON r.id = s.reservation_id
                WHERE r.deadline < clock_timestamp()
                  AND (CAST(:after AS uuid) IS NULL OR s.reservation_id > CAST(:after AS uuid))
                  AND NOT EXISTS (
                      SELECT 1 FROM inspection_capture_receipt c WHERE c.reservation_id = s.reservation_id
                  )
                ORDER BY s.reservation_id LIMIT :limit
            """), {"after": after, "limit": limit})).all())
