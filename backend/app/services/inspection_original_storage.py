"""Write-once Gate 1 originals for a single Linux host with a durable local volume."""
import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol
from uuid import UUID

from fastapi import HTTPException


MAX_ORIGINAL_BYTES = 10 * 1024 * 1024
_HEADER_SIZE = 28  # fixed ISO UTC timestamp with microseconds and newline


@dataclass(frozen=True)
class StoredInspectionOriginal:
    object_key: str
    content: bytes
    received_at: datetime
    backend_id: str = "legacy"


class InspectionOriginalStorage(Protocol):
    async def read_original(self, reservation_id: UUID) -> StoredInspectionOriginal: ...

    async def store_original(
        self, reservation_id: UUID, content: bytes, *, expected_digest: str,
        expected_length: int, deadline: datetime,
    ) -> StoredInspectionOriginal: ...

    async def abandon_original(self, reservation_id: UUID) -> None: ...

    async def read_finalized(self, backend_id: str, reference: str, *, length: int, digest: str) -> bytes: ...


def sync_directory(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class LocalInspectionStorage:
    """Use a per-reservation file lock and permanent tombstones on one filesystem."""

    def __init__(self, root: Path):
        self.root = root

    @contextmanager
    def _locked_directory(self, reservation_id: UUID):
        import fcntl  # Local adapter runs on Linux; hosted defaults stay unavailable.

        try:
            directory = self.root / str(reservation_id)
            directory.mkdir(mode=0o700, exist_ok=True)
            sync_directory(self.root)
            with (directory / "lock").open("ab") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                yield directory
        except OSError as error:
            raise HTTPException(503, "INSPECTION_STORAGE_UNAVAILABLE") from error

    def _read(self, reservation_id: UUID, path: Path) -> StoredInspectionOriginal:
        with path.open("rb") as file:
            header = file.read(_HEADER_SIZE)
            content = file.read(MAX_ORIGINAL_BYTES + 1)
        try:
            if len(header) != _HEADER_SIZE or not header.endswith(b"Z\n"):
                raise ValueError("invalid stored receipt")
            received_at = datetime.fromisoformat(header[:-2].decode() + "+00:00")
        except (ValueError, UnicodeError) as error:
            raise HTTPException(503, "INSPECTION_STORAGE_CORRUPT") from error
        if not content or len(content) > MAX_ORIGINAL_BYTES:
            raise HTTPException(503, "INSPECTION_STORAGE_CORRUPT")
        return StoredInspectionOriginal(f"inspection/{reservation_id}/original", content, received_at)

    def _read_original(self, reservation_id: UUID) -> StoredInspectionOriginal:
        with self._locked_directory(reservation_id) as directory:
            if (directory / "abandoned").exists():
                raise HTTPException(410, "CAPTURE_RESERVATION_ABANDONED")
            path = directory / "original"
            if not path.is_file():
                raise HTTPException(409, "CAPTURE_ORIGINAL_NOT_STORED")
            sync_directory(directory)
            return self._read(reservation_id, path)

    async def read_original(self, reservation_id: UUID) -> StoredInspectionOriginal:
        return await asyncio.to_thread(self._read_original, reservation_id)

    def _store(
        self, reservation_id: UUID, content: bytes, expected_digest: str,
        expected_length: int, deadline: datetime,
    ) -> StoredInspectionOriginal:
        if not content or len(content) > MAX_ORIGINAL_BYTES or len(content) != expected_length:
            raise HTTPException(422, "CAPTURE_CONTENT_MISMATCH")
        if sha256(content).hexdigest() != expected_digest:
            raise HTTPException(422, "CAPTURE_CONTENT_MISMATCH")
        with self._locked_directory(reservation_id) as directory:
            if (directory / "abandoned").exists():
                raise HTTPException(410, "CAPTURE_RESERVATION_ABANDONED")
            path = directory / "original"
            if path.is_file():
                stored = self._read(reservation_id, path)
                if stored.content != content:
                    raise HTTPException(409, "INSPECTION_ORIGINAL_CONFLICT")
                sync_directory(directory)
                return stored
            temporary = None
            try:
                with NamedTemporaryFile(dir=directory, prefix=".upload-", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(b" " * _HEADER_SIZE)
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                    # Timestamp only after all original bytes are fsynced. Publish
                    # the bytes and their timestamp together through a no-clobber link.
                    received_at = datetime.now(timezone.utc)
                    if received_at > deadline:
                        raise HTTPException(410, "VISIT_EXPIRED")
                    header = received_at.isoformat(timespec="microseconds").replace("+00:00", "Z") + "\n"
                    stream.seek(0)
                    stream.write(header.encode("ascii"))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.link(temporary, path)
                sync_directory(directory)
                return StoredInspectionOriginal(f"inspection/{reservation_id}/original", content, received_at)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

    async def store_original(
        self, reservation_id: UUID, content: bytes, *, expected_digest: str,
        expected_length: int, deadline: datetime,
    ) -> StoredInspectionOriginal:
        return await asyncio.to_thread(self._store, reservation_id, content,
                                       expected_digest, expected_length, deadline)

    def _abandon(self, reservation_id: UUID) -> None:
        with self._locked_directory(reservation_id) as directory:
            with (directory / "abandoned").open("ab") as marker:
                os.fsync(marker.fileno())
            sync_directory(directory)
            (directory / "original").unlink(missing_ok=True)
            for temporary in directory.glob(".upload-*"):
                temporary.unlink()
            sync_directory(directory)

    async def abandon_original(self, reservation_id: UUID) -> None:
        await asyncio.to_thread(self._abandon, reservation_id)


class UnavailableInspectionStorage:
    async def read_finalized(self, backend_id: str, reference: str, *, length: int, digest: str) -> bytes:
        raise HTTPException(503, "INSPECTION_STORAGE_UNAVAILABLE")

    async def read_original(self, reservation_id: UUID) -> StoredInspectionOriginal:
        raise HTTPException(503, "INSPECTION_STORAGE_UNAVAILABLE")

    async def store_original(self, reservation_id: UUID, content: bytes, **kwargs) -> StoredInspectionOriginal:
        raise HTTPException(503, "INSPECTION_STORAGE_UNAVAILABLE")

    async def abandon_original(self, reservation_id: UUID) -> None:
        raise HTTPException(503, "INSPECTION_STORAGE_UNAVAILABLE")


def get_inspection_original_storage() -> InspectionOriginalStorage:
    active = os.getenv("INSPECTION_ORIGINAL_BACKEND")
    if not active:
        return UnavailableInspectionStorage()

    from app.core.database import AsyncSessionLocal
    from app.services.inspection_cloudinary_storage import CloudinaryOriginalStore
    from app.services.inspection_local_backend import LocalPermanentOriginalStore
    from app.services.inspection_postgres_staging import PostgresOriginalStaging
    from app.services.inspection_storage_backends import StagedInspectionStorage

    def configured_locations(prefix):
        local_root = os.getenv(f"{prefix}_FILESYSTEM_ROOT")
        if local_root:
            yield "filesystem", LocalPermanentOriginalStore(Path(local_root))
        cloud = os.getenv(f"{prefix}_CLOUDINARY_CLOUD")
        if cloud:
            yield "cloudinary", CloudinaryOriginalStore(
                cloud=cloud, folder=os.environ[f"{prefix}_CLOUDINARY_FOLDER"],
                key=os.environ[f"{prefix}_CLOUDINARY_KEY"], secret=os.environ[f"{prefix}_CLOUDINARY_SECRET"],
            )

    primary = dict(configured_locations("INSPECTION"))
    if active not in primary:
        raise ValueError("Invalid active inspection storage provider")
    active_location = primary[active].backend_id
    stores = {store.backend_id: store for store in primary.values()}
    for prefix in filter(None, os.getenv("INSPECTION_RETAINED_STORE_PREFIXES", "").split(",")):
        for _, store in configured_locations(prefix.strip()):
            stores.setdefault(store.backend_id, store)
    max_bytes = int(os.getenv("INSPECTION_MAX_ORIGINAL_BYTES", str(MAX_ORIGINAL_BYTES)))
    if not 1 <= max_bytes <= MAX_ORIGINAL_BYTES:
        raise ValueError("Inspection original limit exceeds the database limit")
    staging = PostgresOriginalStaging(
        AsyncSessionLocal, quota_bytes=int(os.getenv("INSPECTION_STAGING_QUOTA_BYTES", str(256 * 1024 * 1024))),
    )
    return StagedInspectionStorage(staging, stores, active_location, max_bytes=max_bytes)
