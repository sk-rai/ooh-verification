"""Shared permanent-original contract tests. Live Cloudinary is opt-in."""
import asyncio
import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from fastapi import HTTPException

from app.services.inspection_cloudinary_storage import CloudinaryOriginalStore
from app.services.inspection_local_backend import LocalPermanentOriginalStore
from app.services.inspection_storage_backends import StagedInspectionStorage, StagedOriginal


class OriginalBackendContract(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, store):
        reservation = uuid4()
        original = b"synthetic Gate 1 original storage contract"
        changed = b"x" * len(original)
        with self.assertRaises(HTTPException) as missing:
            await store.retrieve(reservation, limit=len(original))
        self.assertEqual(missing.exception.detail, "CAPTURE_ORIGINAL_NOT_STORED")
        try:
            await asyncio.gather(*(store.create_if_absent(reservation, original) for _ in range(2)))
            self.assertEqual(await store.retrieve(reservation, limit=len(original)), original)
            await store.create_if_absent(reservation, original)
            try:
                await store.create_if_absent(reservation, changed)
            except HTTPException as collision:
                self.assertEqual(collision.status_code, 409)
            self.assertEqual(await store.retrieve(reservation, limit=len(original)), original)
            with self.assertRaises(HTTPException):
                await store.retrieve(reservation, limit=len(original) - 1)
        finally:
            await store.delete_abandoned(reservation)
        await store.delete_abandoned(reservation)
        with self.assertRaises(HTTPException):
            await store.retrieve(reservation, limit=len(original))

    async def test_filesystem(self):
        with TemporaryDirectory() as folder:
            await self.exercise(LocalPermanentOriginalStore(Path(folder)))

    async def test_lost_provider_response_reconciles(self):
        class LostResponseStore(LocalPermanentOriginalStore):
            async def create_if_absent(self, reservation_id, content):
                await super().create_if_absent(reservation_id, content)
                raise HTTPException(503, "synthetic response loss")

        class FixtureStaging:
            async def accept(self, reservation_id, content, backend_id):
                return StagedOriginal(backend_id, content, timestamp)

        content = b"synthetic lost response"
        timestamp = datetime.now(timezone.utc)
        with TemporaryDirectory() as folder:
            store = LostResponseStore(Path(folder))
            storage = StagedInspectionStorage(
                FixtureStaging(), {store.backend_id: store}, store.backend_id, max_bytes=1024,
            )
            result = await storage.store_original(
                uuid4(), content, expected_length=len(content), expected_digest=sha256(content).hexdigest(),
                deadline=timestamp,
            )
            self.assertEqual((result.content, result.received_at), (content, timestamp))

    @unittest.skipUnless(os.getenv("GATE1_CLOUDINARY_CONTRACT_STDIN") == "1", "Requires isolated Cloudinary credentials")
    async def test_cloudinary(self):
        info = json.load(sys.stdin)
        if info["key"] != "898598358339722" or info["cleanup_key"] != "939129822226574":
            self.fail("Unexpected Cloudinary feasibility credential")
        store = CloudinaryOriginalStore(cloud="daenxfazf", folder="gate1-feasibility",
                                        key=info["key"], secret=info["secret"],
                                        cleanup_key=info["cleanup_key"], cleanup_secret=info["cleanup_secret"])
        await self.exercise(store)
