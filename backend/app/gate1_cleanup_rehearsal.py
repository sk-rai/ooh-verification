print("GATE1_CLEANUP_START", flush=True)

import asyncio
import os
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.inspection_cloudinary_storage import CloudinaryOriginalStore
from app.services.inspection_postgres_staging import PostgresOriginalStaging
from app.services.inspection_storage_backends import StagedInspectionStorage
from app.services.inspection_storage_cleanup import sweep_inspection_originals

ABANDONED = UUID("fc52eb8d-df86-4ece-b8e6-424c3478e858")
FINALIZED = UUID("dd01e967-72db-4723-9d2d-f8824ef72db0")
HOST = "dpg-dc1a1euq1p3s73fknfu0-a"
DB = "tc_staging_db_mf4a"
ROLE = "tc_gate1_staging_cleanup"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


class RehearsalStaging(PostgresOriginalStaging):
    async def expired_unfinalized(self, *, after, limit):
        rows = await super().expired_unfinalized(after=after, limit=limit)
        require(all(row == ABANDONED for row in rows),
                "Unexpected cleanup candidate. No cleanup performed for that candidate.")
        return rows


async def main():
    url = make_url(os.environ["GATE1_CLEANUP_DATABASE_URL"])
    require(
        (url.drivername, url.host, url.port, url.database, url.username)
        == ("postgresql+asyncpg", HOST, 5432, DB, ROLE),
        "Unexpected staging cleanup connection settings",
    )
    engine = create_async_engine(url, connect_args={"timeout": 10})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as db:
            identity = (await db.execute(text(
                "SELECT current_database(), session_user, current_user"
            ))).one()
            require(tuple(identity) == (DB, ROLE, ROLE),
                    "Unexpected staging cleanup database identity")
            before = (await db.execute(text("""
                SELECT c.evidence_id, c.storage_backend_id, c.storage_reference,
                       r.digest, r.byte_length
                FROM inspection_capture_receipt c
                JOIN inspection_upload_reservation r ON r.id = c.reservation_id
                WHERE c.reservation_id = :id
            """), {"id": FINALIZED})).one()
            abandoned_backend = await db.scalar(text("""
                SELECT backend_id FROM inspection_original_staging
                WHERE reservation_id = :id
            """), {"id": ABANDONED})

        store = CloudinaryOriginalStore(
            cloud="daenxfazf",
            folder="gate1-feasibility",
            key=os.environ["GATE1_CONTRIBUTOR_KEY"],
            secret=os.environ["GATE1_CONTRIBUTOR_SECRET"],
            cleanup_key=os.environ["GATE1_CLEANUP_KEY"],
            cleanup_secret=os.environ["GATE1_CLEANUP_SECRET"],
        )
        require(store.backend_id == abandoned_backend == before.storage_backend_id,
                "Unexpected Cloudinary location pin")

        staging = RehearsalStaging(sessions, quota_bytes=256 * 1024 * 1024)
        storage = StagedInspectionStorage(
            staging, {store.backend_id: store}, store.backend_id,
            max_bytes=10 * 1024 * 1024,
        )
        require(await staging.expired_unfinalized(after=None, limit=2) == [ABANDONED],
                "Expected the expired synthetic reservation")
        print(f"{datetime.now(timezone.utc).isoformat()} starting with cursor=None", flush=True)
        cursor, failures = await sweep_inspection_originals(
            sessions, storage, after=None, limit=1,
        )
        require(cursor == ABANDONED and not failures, "First sweep page failed")
        cursor, failures = await sweep_inspection_originals(
            sessions, storage, after=cursor, limit=1,
        )
        require(cursor is None and not failures, "Sweep did not finish")

        async with sessions() as db:
            result = (await db.execute(text("""
                SELECT s.content IS NULL,
                       EXISTS (SELECT 1 FROM inspection_upload_tombstone t
                               WHERE t.reservation_id = s.reservation_id),
                       NOT EXISTS (SELECT 1 FROM inspection_capture_receipt c
                                   WHERE c.reservation_id = s.reservation_id)
                FROM inspection_original_staging s WHERE s.reservation_id = :id
            """), {"id": ABANDONED})).one()
            require(tuple(result) == (True, True, True),
                    "Unexpected abandoned reservation state")
            after = (await db.execute(text("""
                SELECT evidence_id, storage_backend_id, storage_reference
                FROM inspection_capture_receipt WHERE reservation_id = :id
            """), {"id": FINALIZED})).one()
            require(tuple(after) == tuple(before)[:3], "Finalized receipt changed")

        content = await store.retrieve(FINALIZED, limit=before.byte_length)
        require(len(content) == before.byte_length and
                sha256(content).hexdigest() == before.digest,
                "Finalized original failed SHA-256 verification")
        print("PASS: hosted sweep revisited tombstone and completed both pages")
        print("PASS: finalized receipt and Cloudinary original preserved")
    finally:
        await engine.dispose()


asyncio.run(main())
