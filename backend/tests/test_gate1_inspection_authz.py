"""Integration checks for Gate 1. Run against a disposable migrated database."""
import asyncio
from datetime import datetime, timedelta, timezone
from itertools import count
from uuid import uuid4

import os
import unittest
from fastapi import HTTPException
from sqlalchemy import text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.inspection_authz import lock_vendor_visit, lock_vendor_visit_access, reassign_visit, require_receipt_key, revoke_inspection_key, revoke_visit
from app.models.device_key import DeviceKey
from app.models.client import Client
from app.models.inspection_visit import InspectionVisit
from app.models.tenant_config import TenantConfig
from app.models.vendor import Vendor, VendorStatus



def disposable_url():
    url = make_url(os.environ["TEST_DATABASE_URL"])
    if url.drivername != "postgresql+asyncpg" or url.host not in ("127.0.0.1", "localhost"):
        raise RuntimeError("A loopback disposable PostgreSQL database is required")
    if url.database != "trustcapture_gate1_test":
        raise RuntimeError("Expected the dedicated Gate 1 disposable database")
    return url


async def verify_migration():
    # Keep Alembic-managed triggers and constraints in place for these tests.
    engine = create_async_engine(disposable_url(), poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == "029_inspection_staging"
    finally:
        await engine.dispose()


fixture_number = count(1)


async def seed(sessions, *, expires_at=None):
    tenant, owner, visit, assignment = uuid4(), uuid4(), uuid4(), uuid4()
    number = next(fixture_number)
    vendor = f"G{number:05d}"
    async with sessions.begin() as db:
        db.add(TenantConfig(tenant_id=tenant, tenant_name="Synthetic Gate 1", is_active=True))
        db.add(Client(
            client_id=owner, tenant_id=tenant, company_name="Synthetic Gate 1",
            email=f"{owner}@example.invalid", password_hash="unused", phone_number="+15550102002",
        ))
        await db.flush()
        db.add(Vendor(
            vendor_id=vendor, tenant_id=tenant, created_by_client_id=owner,
            name="Synthetic vendor", phone_number=f"+155501{number:05d}",
        ))
        await db.flush()
        db.add(InspectionVisit(
            id=visit, tenant_id=tenant, owner_client_id=owner, vendor_id=vendor, assignment_id=assignment,
            expires_at=expires_at or datetime.now(timezone.utc) + timedelta(hours=1),
        ))
    return dict(tenant_id=tenant, owner_client_id=owner, vendor_id=vendor,
                visit_id=visit, assignment_id=assignment, generation=1), owner


async def invalidate(db, ids, owner, reason):
    if reason == "tenant":
        await db.execute(update(TenantConfig).where(
            TenantConfig.tenant_id == ids["tenant_id"],
        ).values(is_active=False))
    elif reason == "vendor":
        await db.execute(update(Vendor).where(
            Vendor.vendor_id == ids["vendor_id"],
        ).values(status=VendorStatus.INACTIVE))
    else:
        await revoke_visit(db, tenant_id=ids["tenant_id"], owner_client_id=owner,
                           visit_id=ids["visit_id"], assignment_id=ids["assignment_id"], generation=ids["generation"])
        await db.flush()


async def wait_for_lock(observer, waiter, blocker):
    for _ in range(100):
        if await observer.scalar(text("SELECT :blocker = ANY(pg_blocking_pids(:waiter))"),
                                 {"blocker": blocker, "waiter": waiter}):
            return
        await asyncio.sleep(0.03)
    raise AssertionError("Expected the competing transaction to wait for the first row lock")


async def check_authorization_serializes_with_invalidation(reason, error, authorization_first):
    engine = create_async_engine(disposable_url(), poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        ids, owner = await seed(sessions)
        async with sessions() as first, sessions() as second, sessions() as observer:
            first_pid = await first.scalar(text("SELECT pg_backend_pid()"))
            second_pid = await second.scalar(text("SELECT pg_backend_pid()"))
            if authorization_first:
                await lock_vendor_visit(first, **ids)
                competing = asyncio.create_task(invalidate(second, ids, owner, reason))
            else:
                await invalidate(first, ids, owner, reason)
                competing = asyncio.create_task(lock_vendor_visit(second, **ids))
            try:
                await wait_for_lock(observer, second_pid, first_pid)
                await first.commit()
                if authorization_first:
                    await asyncio.wait_for(competing, 5)
                    await second.commit()
                else:
                    with unittest.TestCase().assertRaises(HTTPException) as denied:
                        await asyncio.wait_for(competing, 5)
                    assert (denied.exception.status_code, denied.exception.detail) == (403, error)
            finally:
                if not competing.done():
                    competing.cancel()
                    await asyncio.gather(competing, return_exceptions=True)
        async with sessions() as db:
            with unittest.TestCase().assertRaises(HTTPException) as denied:
                await lock_vendor_visit(db, **ids)
            assert (denied.exception.status_code, denied.exception.detail) == (403, error)
    finally:
        await engine.dispose()


async def check_visit_owner_scope_and_identity_are_database_enforced():
    engine = create_async_engine(disposable_url(), poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        ids, _ = await seed(sessions)
        _, other_owner = await seed(sessions)
        async with sessions() as db:
            with unittest.TestCase().assertRaises(IntegrityError):
                await db.execute(text("""
                    INSERT INTO inspection_visit (id, tenant_id, owner_client_id, vendor_id, expires_at)
                    VALUES (:id, :tenant, :owner, :vendor, now() + interval '1 hour')
                """), dict(id=uuid4(), tenant=ids["tenant_id"], owner=other_owner, vendor=ids["vendor_id"]))
        async with sessions() as db:
            with unittest.TestCase().assertRaises(DBAPIError) as denied:
                await db.execute(update(InspectionVisit).where(
                    InspectionVisit.id == ids["visit_id"],
                ).values(owner_client_id=other_owner))
            assert denied.exception.orig.sqlstate == "55000"
    finally:
        await engine.dispose()


@unittest.skipUnless(os.getenv("RUN_GATE1_DB_TESTS") == "1", "Requires migrated disposable Gate 1 DB")
class InspectionAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await verify_migration()

    async def test_authorization_races(self):
        for reason, error in (
            ("tenant", "TENANT_INACTIVE"),
            ("vendor", "VENDOR_INACTIVE"),
            ("visit", "VISIT_REVOKED"),
        ):
            for authorization_first in (False, True):
                with self.subTest(reason=reason, authorization_first=authorization_first):
                    await check_authorization_serializes_with_invalidation(reason, error, authorization_first)

    async def test_ownership(self):
        await check_visit_owner_scope_and_identity_are_database_enforced()

    async def test_key_revocation_waits_for_vendor_visit_lock(self):
        engine = create_async_engine(disposable_url(), poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            ids, _ = await seed(sessions)
            key_id = uuid4()
            key_scope = dict(key_id=key_id, tenant_id=ids["tenant_id"], vendor_id=ids["vendor_id"])
            async with sessions.begin() as db:
                db.add(DeviceKey(**key_scope, public_key="fixture-only", key_fingerprint="a" * 64,
                                 inspection_enrollment_id=uuid4()))
            async with sessions() as first, sessions() as second, sessions() as observer:
                first_pid = await first.scalar(text("SELECT pg_backend_pid()"))
                second_pid = await second.scalar(text("SELECT pg_backend_pid()"))
                visit = await lock_vendor_visit(first, **ids)
                receipt_time = datetime.now(timezone.utc)
                await require_receipt_key(first, visit=visit, key_id=key_id, received_at=receipt_time)
                revocation = asyncio.create_task(revoke_inspection_key(second, **key_scope))
                try:
                    await wait_for_lock(observer, second_pid, first_pid)
                    await first.commit()
                    await asyncio.wait_for(revocation, 5)
                    await second.commit()
                finally:
                    if not revocation.done():
                        revocation.cancel()
                        await asyncio.gather(revocation, return_exceptions=True)
            async with sessions() as db:
                key = await db.get(DeviceKey, key_id)
                self.assertIsNotNone(key.revoked_at)
                visit = await lock_vendor_visit(db, **ids)
                with self.assertRaises(HTTPException) as denied:
                    await require_receipt_key(db, visit=visit, key_id=key_id, received_at=receipt_time)
                self.assertEqual(denied.exception.detail, "EVIDENCE_KEY_REVOKED")
        finally:
            await engine.dispose()

    async def test_reassignment_race_and_return_to_original_vendor(self):
        engine = create_async_engine(disposable_url(), poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            for authorization_first in (False, True):
                with self.subTest(authorization_first=authorization_first):
                    ids, owner = await seed(sessions)
                    number = next(fixture_number)
                    second_vendor = f"G{number:05d}"
                    async with sessions.begin() as db:
                        db.add(Vendor(
                            vendor_id=second_vendor, tenant_id=ids["tenant_id"],
                            created_by_client_id=owner, name="Replacement vendor",
                            phone_number=f"+155501{number:05d}",
                        ))
                    owner_scope = {k: v for k, v in ids.items() if k != "vendor_id"}
                    async with sessions() as first, sessions() as second, sessions() as observer:
                        first_pid = await first.scalar(text("SELECT pg_backend_pid()"))
                        second_pid = await second.scalar(text("SELECT pg_backend_pid()"))
                        if authorization_first:
                            await lock_vendor_visit(first, **ids)
                            pending = asyncio.create_task(reassign_visit(
                                second, **owner_scope, new_vendor_id=second_vendor,
                            ))
                        else:
                            moved = await reassign_visit(first, **owner_scope, new_vendor_id=second_vendor)
                            pending = asyncio.create_task(lock_vendor_visit(second, **ids))
                        try:
                            await wait_for_lock(observer, second_pid, first_pid)
                            await first.commit()
                            if authorization_first:
                                moved = await asyncio.wait_for(pending, 5)
                                await second.commit()
                            else:
                                with self.assertRaises(HTTPException) as error:
                                    await asyncio.wait_for(pending, 5)
                                self.assertEqual((error.exception.status_code, error.exception.detail),
                                                 (404, "VISIT_NOT_FOUND"))
                        finally:
                            if not pending.done():
                                pending.cancel()
                                await asyncio.gather(pending, return_exceptions=True)

                    async with sessions.begin() as db:
                        returned = await reassign_visit(
                            db, **dict(owner_scope, assignment_id=moved.assignment_id,
                                       generation=moved.generation), new_vendor_id=ids["vendor_id"],
                        )
                    self.assertEqual(returned.generation, 3)
                    self.assertNotEqual(returned.assignment_id, ids["assignment_id"])
                    async with sessions() as db:
                        with self.assertRaises(HTTPException) as stale:
                            await lock_vendor_visit(db, **ids)
                        self.assertEqual((stale.exception.status_code, stale.exception.detail),
                                         (409, "ASSIGNMENT_GENERATION_STALE"))
                    async with sessions() as db:
                        await lock_vendor_visit(db, **dict(ids, assignment_id=returned.assignment_id, generation=3))
                        rows = (await db.execute(text("""
                            SELECT generation, id FROM inspection_assignment
                            WHERE visit_id = :visit ORDER BY generation
                        """), {"visit": ids["visit_id"]})).all()
                        self.assertEqual([tuple(row) for row in rows], [
                            (1, ids["assignment_id"]), (2, moved.assignment_id), (3, returned.assignment_id),
                        ])
        finally:
            await engine.dispose()

    async def test_access_scope_and_terminal_visit(self):
        engine = create_async_engine(disposable_url(), poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            ids, _ = await seed(sessions)
            owner, other_vendor = uuid4(), "OTHER1"
            async with sessions.begin() as db:
                db.add(Client(
                    client_id=owner, tenant_id=ids["tenant_id"], company_name="Other owner",
                    email=f"{owner}@example.invalid", password_hash="unused", phone_number="+15550108900",
                ))
                await db.flush()
                db.add(Vendor(
                    vendor_id=other_vendor, tenant_id=ids["tenant_id"], created_by_client_id=owner,
                    name="Other vendor", phone_number="+15550108901",
                ))
            for wrong, expected in (
                (dict(ids, owner_client_id=owner), (404, "VISIT_NOT_FOUND")),
                (dict(ids, vendor_id=other_vendor), (404, "VISIT_NOT_FOUND")),
                (dict(ids, assignment_id=uuid4()), (409, "ASSIGNMENT_GENERATION_STALE")),
            ):
                async with sessions() as db:
                    with self.assertRaises(HTTPException) as denied:
                        await lock_vendor_visit_access(db, **wrong)
                    self.assertEqual((denied.exception.status_code, denied.exception.detail), expected)
            async with sessions.begin() as db:
                visit = await lock_vendor_visit(db, **ids)
                visit.submitted_at = datetime.now(timezone.utc)
            owner_scope = {k: v for k, v in ids.items() if k != "vendor_id"}
            async with sessions() as db:
                await lock_vendor_visit_access(db, **ids)
                for operation in (
                    lambda: lock_vendor_visit(db, **ids),
                    lambda: revoke_visit(db, **owner_scope),
                    lambda: reassign_visit(db, **owner_scope, new_vendor_id=other_vendor),
                ):
                    with self.assertRaises(HTTPException) as denied:
                        await operation()
                    self.assertEqual(denied.exception.detail, "VISIT_ALREADY_SUBMITTED")
            expired, _ = await seed(sessions, expires_at=datetime.now(timezone.utc) - timedelta(days=1))
            async with sessions() as db:
                await lock_vendor_visit_access(db, **expired)
                with self.assertRaises(HTTPException) as denied:
                    await lock_vendor_visit(db, **expired)
                self.assertEqual(denied.exception.status_code, 410)
                with self.assertRaises(DBAPIError) as immutable:
                    await db.execute(update(InspectionVisit).where(
                        InspectionVisit.id == expired["visit_id"],
                    ).values(expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
                self.assertEqual(immutable.exception.orig.sqlstate, "55000")
        finally:
            await engine.dispose()

    async def test_history_writes_require_the_trigger(self):
        engine = create_async_engine(disposable_url(), poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            ids, _ = await seed(sessions)
            async with sessions.begin() as db:
                await db.execute(text("CREATE ROLE gate1_history_runtime NOLOGIN"))
                await db.execute(text("GRANT USAGE ON SCHEMA public TO gate1_history_runtime"))
                await db.execute(text("GRANT SELECT, UPDATE ON inspection_visit TO gate1_history_runtime"))
                await db.execute(text("GRANT SELECT ON inspection_assignment TO gate1_history_runtime"))
                await db.execute(text("SET LOCAL ROLE gate1_history_runtime"))
                await db.execute(text("""
                    UPDATE inspection_visit SET generation = 2, assignment_id = gen_random_uuid()
                    WHERE id = :visit
                """), {"visit": ids["visit_id"]})
                self.assertEqual(await db.scalar(text("""
                    SELECT count(*) FROM inspection_assignment WHERE visit_id = :visit
                """), {"visit": ids["visit_id"]}), 2)
            await seed(sessions)
            for sql in (
                "TRUNCATE inspection_assignment",
                "INSERT INTO inspection_assignment SELECT gen_random_uuid(), visit_id, generation + 20,"
                " tenant_id, vendor_id FROM inspection_assignment LIMIT 1",
            ):
                async with sessions() as db:
                    await db.execute(text("SET LOCAL ROLE gate1_history_runtime"))
                    with self.assertRaises(DBAPIError) as denied:
                        await db.execute(text(sql))
                    self.assertEqual(denied.exception.orig.sqlstate, "42501")
            async with sessions() as db:
                with self.assertRaises(IntegrityError) as denied:
                    await db.execute(text("""
                        INSERT INTO inspection_assignment (id, visit_id, generation, tenant_id, vendor_id)
                        SELECT gen_random_uuid(), :visit, 51, tenant_id, vendor_id
                        FROM inspection_assignment WHERE visit_id <> :visit LIMIT 1
                    """), {"visit": ids["visit_id"]})
                self.assertEqual(denied.exception.orig.sqlstate, "23503")
        finally:
            await engine.dispose()

    async def test_enrollment_endpoint_authentication_and_legacy_isolation(self):
        from base64 import b64encode
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient
        from sqlalchemy import select
        from app.api.auth import router
        from app.core.database import get_db
        from app.core.security import create_access_token
        from app.services.device_key_service import get_keys_for_vendor, register_key_version
        from app.services.inspection_enrollment import issue_enrollment_proof

        engine = create_async_engine(disposable_url(), poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        app = FastAPI()
        app.include_router(router)

        async def session():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = session
        try:
            ids, _ = await seed(sessions)
            other, _ = await seed(sessions)
            private_key = ec.generate_private_key(ec.SECP256R1())
            public_key = private_key.public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode()
            async with sessions.begin() as db:
                vendor = await db.get(Vendor, ids["vendor_id"])
                vendor.device_id = "synthetic-enrolled-device"
                vendor.device_verified = True
                proof = issue_enrollment_proof(vendor)
            signature = b64encode(private_key.sign(proof.encode(), ec.ECDSA(hashes.SHA256()))).decode()
            body = dict(device_id="synthetic-enrolled-device", public_key=public_key,
                        enrollment_proof=proof, proof_signature=signature)

            def headers(vendor_id):
                token = create_access_token(dict(sub=vendor_id, type="vendor", vendor_id=vendor_id))
                return {"Authorization": f"Bearer {token}"}

            path = "/api/auth/vendor/inspection-device"
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                self.assertIn((await client.post(path, json=body)).status_code, (401, 403))
                self.assertEqual((await client.post(path, json=body, headers=headers(other["vendor_id"]))).status_code, 403)
                actor_headers = headers(ids["vendor_id"])
                wrong = await client.post(path, json=dict(body, device_id="different"), headers=actor_headers)
                self.assertEqual(wrong.json()["detail"], "INSPECTION_ENROLLMENT_PROOF_INVALID")
                async with sessions.begin() as db:
                    await invalidate(db, ids, ids["owner_client_id"], "vendor")
                inactive = await client.post(path, json=body, headers=actor_headers)
                self.assertEqual(inactive.json()["detail"], "VENDOR_INACTIVE")
                async with sessions.begin() as db:
                    await db.execute(update(Vendor).where(
                        Vendor.vendor_id == ids["vendor_id"],
                    ).values(status=VendorStatus.ACTIVE))
                    self.assertIsNone(await db.scalar(select(DeviceKey.key_id).where(
                        DeviceKey.vendor_id == ids["vendor_id"],
                    )))
                accepted = await client.post(path, json=body, headers=actor_headers)
                self.assertEqual(accepted.status_code, 201, accepted.text)
                consumed = await client.post(path, json=body, headers=actor_headers)
                self.assertEqual(consumed.json()["detail"], "INSPECTION_ENROLLMENT_PROOF_INVALID")
            async with sessions.begin() as db:
                await register_key_version(
                    db, vendor_id=ids["vendor_id"], tenant_id=ids["tenant_id"],
                    device_id=body["device_id"], public_key_pem=public_key,
                )
                await db.flush()
                legacy = await get_keys_for_vendor(db, ids["vendor_id"])
                self.assertEqual(len(legacy), 1)
                self.assertIsNone(legacy[0].inspection_enrollment_id)
                trusted = (await db.scalars(select(DeviceKey).where(
                    DeviceKey.vendor_id == ids["vendor_id"], DeviceKey.inspection_enrollment_id.is_not(None),
                ))).all()
                self.assertEqual(len(trusted), 1)
                self.assertEqual(str(trusted[0].key_id), accepted.json()["key_id"])
                self.assertIsNone(trusted[0].active_to)
        finally:
            await engine.dispose()

    async def test_receipt_verification_serializes_with_revocation(self):
        from base64 import b64encode
        from hashlib import sha256
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from app.services.device_key_service import compute_key_fingerprint
        from app.services.inspection_receipt import verify_inspection_original

        engine = create_async_engine(disposable_url(), poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        original = b"synthetic original bytes"
        digest = sha256(original).hexdigest()
        signature = b64encode(private_key.sign(digest.encode(), ec.ECDSA(hashes.SHA256()))).decode()
        try:
            for verification_first in (False, True):
                with self.subTest(verification_first=verification_first):
                    ids, _ = await seed(sessions)
                    key_scope = dict(tenant_id=ids["tenant_id"], vendor_id=ids["vendor_id"], key_id=uuid4())
                    async with sessions.begin() as db:
                        db.add(DeviceKey(
                            **key_scope, public_key=public_key, inspection_enrollment_id=uuid4(),
                            key_fingerprint=compute_key_fingerprint(public_key),
                        ))

                    async def verify(db, **changes):
                        visit = await lock_vendor_visit(db, **ids)
                        inputs = dict(
                            visit=visit, key_id=key_scope["key_id"], original=original,
                            received_at=await db.scalar(text("SELECT clock_timestamp()")),
                            expected_digest=digest, expected_length=len(original), signature_b64=signature,
                            deadline=visit.expires_at,
                        )
                        return await verify_inspection_original(db, **(inputs | changes))

                    async with sessions() as first, sessions() as second, sessions() as observer:
                        first_pid = await first.scalar(text("SELECT pg_backend_pid()"))
                        second_pid = await second.scalar(text("SELECT pg_backend_pid()"))
                        if verification_first:
                            for change, expected in (
                                ({"original": b"changed"}, "CAPTURE_CONTENT_MISMATCH"),
                                ({"signature_b64": "invalid!"}, "CAPTURE_SIGNATURE_INVALID"),
                            ):
                                with self.assertRaises(HTTPException) as invalid:
                                    await verify(first, **change)
                                self.assertEqual(invalid.exception.detail, expected)
                            boundary = datetime.now(timezone.utc)
                            await verify(first, received_at=boundary, deadline=boundary)
                            with self.assertRaises(HTTPException) as late:
                                await verify(first, received_at=boundary, deadline=boundary - timedelta(microseconds=1))
                            self.assertEqual(late.exception.status_code, 410)
                            receipt = await verify(first)
                            self.assertEqual((receipt.digest, receipt.key_id), (digest, key_scope["key_id"]))
                            competing = asyncio.create_task(revoke_inspection_key(second, **key_scope))
                        else:
                            await revoke_inspection_key(first, **key_scope)
                            competing = asyncio.create_task(verify(second))
                        try:
                            await wait_for_lock(observer, second_pid, first_pid)
                            await first.commit()
                            if verification_first:
                                await asyncio.wait_for(competing, 5)
                                await second.commit()
                            else:
                                with self.assertRaises(HTTPException) as denied:
                                    await asyncio.wait_for(competing, 5)
                                self.assertEqual(denied.exception.detail, "EVIDENCE_KEY_REVOKED")
                        finally:
                            if not competing.done():
                                competing.cancel()
                                await asyncio.gather(competing, return_exceptions=True)
        finally:
            await engine.dispose()

    async def test_pinned_package_and_exact_reservation_endpoint(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        from uuid import UUID
        from base64 import b64encode
        from hashlib import sha256
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from fastapi import FastAPI, Request
        from httpx import ASGITransport, AsyncClient, ReadError
        from app.api.inspection_capture import router
        from app.core.database import get_db
        from app.core.security import create_access_token
        from app.services.device_key_service import compute_key_fingerprint
        from app.services.inspection_capture import clean_expired_inspection_original
        from app.services.inspection_original_storage import (
            LocalInspectionStorage, StoredInspectionOriginal, get_inspection_original_storage,
        )

        engine = create_async_engine(disposable_url(), poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        app = FastAPI()
        app.include_router(router)

        async def session(request: Request):
            async with sessions() as db:
                if request.url.path.endswith("/submit"):
                    await db.execute(text("SET ROLE gate1_submit_runtime"))
                yield db

        app.dependency_overrides[get_db] = session
        try:
            async with sessions.begin() as db:
                for statement in (
                    "CREATE ROLE gate1_submit_runtime NOLOGIN",
                    "GRANT USAGE ON SCHEMA public TO gate1_submit_runtime",
                    "GRANT SELECT ON tenant_config, vendors, inspection_visit, inspection_workflow_version, "
                    "inspection_document_requirement, inspection_document_instance, inspection_form_version, "
                    "inspection_capture_target, inspection_upload_reservation, inspection_capture_receipt, "
                    "device_keys, evidence TO gate1_submit_runtime",
                    "GRANT UPDATE (is_active) ON tenant_config TO gate1_submit_runtime",
                    "GRANT UPDATE (status) ON vendors TO gate1_submit_runtime",
                    "GRANT UPDATE (revision, submitted_at) ON inspection_visit TO gate1_submit_runtime",
                    "GRANT SELECT, INSERT ON inspection_document_revision, inspection_visit_submission, "
                    "inspection_submission_document TO gate1_submit_runtime",
                    "GRANT UPDATE (sealed) ON inspection_visit_submission TO gate1_submit_runtime",
                ):
                    await db.execute(text(statement))
            ids, _ = await seed(sessions)
            form, document, item_one, item_two, target, key_id = (uuid4() for _ in range(6))
            workflow, requirement = uuid4(), uuid4()
            original = b"synthetic slot original"
            cloud_fixture = None
            if os.getenv("GATE1_CLOUDINARY_ENDPOINT_STDIN") == "1":
                import sys
                from base64 import b64decode
                from app.services.inspection_cloudinary_storage import CloudinaryOriginalStore

                cloud_credentials = json.load(sys.stdin)
                if cloud_credentials["key"] != "898598358339722":
                    self.fail("Expected the approved isolated Cloudinary Contributor credential")

                class ExistingCloudinaryFixture(CloudinaryOriginalStore):
                    def _id(self, reservation_id):
                        if reservation_id not in staged_reservations:
                            raise AssertionError("Unexpected Cloudinary reservation")
                        return "gate1-feasibility/808806bd10da4a4db62fc2992e7cf274/race.png"

                    async def create_if_absent(self, reservation_id, content):
                        self._id(reservation_id)
                        raise AssertionError("This endpoint fixture permits only read-back of the existing object")

                cloud_fixture = ExistingCloudinaryFixture(
                    cloud="daenxfazf", folder="gate1-feasibility",
                    key=cloud_credentials["key"], secret=cloud_credentials["secret"],
                )
                original = b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGMQDewBAAFxAPNwhUMnAAAAAElFTkSuQmCC")
            digest = sha256(original).hexdigest()
            private_key = ec.generate_private_key(ec.SECP256R1())
            pem = private_key.public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode()
            signature = b64encode(private_key.sign(digest.encode(), ec.ECDSA(hashes.SHA256()))).decode()
            reads = []

            before_read = {}
            directory = TemporaryDirectory()
            self.addCleanup(directory.cleanup)
            disk = LocalInspectionStorage(Path(directory.name))
            from app.services.inspection_local_backend import LocalPermanentOriginalStore
            from app.services.inspection_postgres_staging import PostgresOriginalStaging
            from app.services.inspection_storage_backends import StagedInspectionStorage

            staging = PostgresOriginalStaging(sessions, quota_bytes=1024 * 1024)
            permanent = LocalPermanentOriginalStore(Path(directory.name))
            def staged_storage():
                if cloud_fixture is not None:
                    return StagedInspectionStorage(staging, {cloud_fixture.backend_id: cloud_fixture}, cloud_fixture.backend_id, max_bytes=1024)
                return StagedInspectionStorage(staging, {permanent.backend_id: permanent}, permanent.backend_id, max_bytes=1024)

            staged_reservations = set()
            disk_reservations = set()
            missing_timestamp = set()
            parallel_reservation = None
            parallel_ready = asyncio.Event()
            staging_purged = asyncio.Event()
            parallel_reads = 0

            finalized_bytes_read = asyncio.Event()
            release_finalized_read = asyncio.Event()

            class FixtureStorage:
                async def read_finalized(self, backend_id, reference, *, length, digest):
                    content = await staged_storage().read_finalized(
                        backend_id, reference, length=length, digest=digest,
                    )
                    finalized_bytes_read.set()
                    await asyncio.wait_for(release_finalized_read.wait(), 5)
                    return content

                async def store_original(self, reservation_id, content, **kwargs):
                    storage = staged_storage() if reservation_id in staged_reservations else disk
                    return await storage.store_original(reservation_id, content, **kwargs)
                abandon_original = disk.abandon_original

                async def read_original(self, reservation_id):
                    nonlocal parallel_reads
                    reads.append(reservation_id)
                    if reservation_id == parallel_reservation:
                        parallel_reads += 1
                        if parallel_reads == 2:
                            parallel_ready.set()
                        first_reader = parallel_reads == 1
                        await asyncio.wait_for(parallel_ready.wait(), 5)
                        if not first_reader:
                            await asyncio.wait_for(staging_purged.wait(), 12)
                    callback = before_read.pop(reservation_id, None)
                    if callback is not None:
                        await callback()
                    if reservation_id in missing_timestamp:
                        return SimpleNamespace(object_key=f"synthetic/{reservation_id}", content=original)
                    if reservation_id in staged_reservations:
                        return await staged_storage().read_original(reservation_id)
                    if reservation_id in disk_reservations:
                        return await disk.read_original(reservation_id)
                    return StoredInspectionOriginal(
                        f"synthetic/{reservation_id}", original, datetime.now(timezone.utc),
                    )

            app.dependency_overrides[get_inspection_original_storage] = FixtureStorage
            async with sessions.begin() as db:
                db.add(DeviceKey(
                    key_id=key_id, tenant_id=ids["tenant_id"], vendor_id=ids["vendor_id"],
                    public_key=pem, key_fingerprint=compute_key_fingerprint(pem),
                    inspection_enrollment_id=uuid4(),
                ))
                await db.execute(text("""
                    INSERT INTO inspection_form_version (id, tenant_id, owner_client_id, definition)
                    VALUES (:form, :tenant_id, :owner_client_id, CAST(:definition AS jsonb))
                """), ids | {"form": form, "definition": json.dumps({
                    "repeat_items": [str(item_one), str(item_two)],
                    "repeat_fields": {"measurement": {"type": "number", "required": True, "scale": 2, "unit": "mm"}},
                })})
                await db.execute(text("""
                    INSERT INTO inspection_workflow_version (id, tenant_id, owner_client_id)
                    VALUES (:workflow, :tenant_id, :owner_client_id)
                """), ids | {"workflow": workflow})
                await db.execute(text("""
                    INSERT INTO inspection_document_requirement (
                        id, workflow_version_id, tenant_id, owner_client_id, form_version_id,
                        position, min_instances, max_instances
                    ) VALUES (:requirement, :workflow, :tenant_id, :owner_client_id, :form, 1, 1, 1)
                """), ids | {"workflow": workflow, "requirement": requirement, "form": form})
                await db.execute(text("""
                    UPDATE inspection_workflow_version SET published_at = clock_timestamp()
                    WHERE id = :workflow
                """), {"workflow": workflow})
                await db.execute(text("""
                    UPDATE inspection_visit SET workflow_version_id = :workflow WHERE id = :visit_id
                """), ids | {"workflow": workflow})
                await db.execute(text("""
                    INSERT INTO inspection_document_instance
                        (id, visit_id, tenant_id, owner_client_id, form_version_id, ordinal,
                         workflow_version_id, requirement_id, instance_number)
                    VALUES (:document, :visit_id, :tenant_id, :owner_client_id, :form, 1,
                            :workflow, :requirement, 1)
                """), ids | {"document": document, "form": form,
                              "workflow": workflow, "requirement": requirement})
                await db.execute(text("""
                    INSERT INTO inspection_capture_target
                        (id, document_instance_id, visit_id, field_id, slot_id, repeat_item_id, required)
                    VALUES (:target, :document, :visit_id, 'observation', 'photo', :item, true)
                """), ids | {"target": target, "document": document, "item": item_two})

                await db.execute(text("""
                    UPDATE inspection_visit SET package_sealed_at = clock_timestamp() WHERE id = :visit_id
                """), ids)
            async with sessions() as db:
                with self.assertRaises(DBAPIError) as sealed:
                    await db.execute(text("""
                        INSERT INTO inspection_capture_target
                            (id, document_instance_id, visit_id, field_id, slot_id, repeat_item_id)
                        VALUES (:target, :document, :visit_id, 'observation', 'photo', :item)
                    """), ids | {"target": uuid4(), "document": document, "item": item_one})
                self.assertEqual(sealed.exception.orig.sqlstate, "55000")

            vendor_id = ids["vendor_id"]
            token = create_access_token(dict(sub=vendor_id, type="vendor", vendor_id=vendor_id))
            headers = {"Authorization": f"Bearer {token}"}
            path = f"/api/inspection-visits/{ids['visit_id']}"
            scope = dict(owner_client_id=str(ids["owner_client_id"]),
                         assignment_id=str(ids["assignment_id"]), generation=1)
            capture = scope | dict(
                document_instance_id=str(document), field_id="observation", slot_id="photo",
                repeat_item_id=str(item_two), client_capture_id=str(uuid4()),
                upload_key="synthetic-reservation", digest=digest, byte_length=len(original),
            )
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                package = await client.get(path + "/package", params=scope, headers=headers)
                self.assertEqual(package.status_code, 200)
                self.assertEqual(package.json()["code"], "PACKAGE_READY")
                self.assertEqual(package.json()["documents"][0]["definition"]["repeat_items"],
                                 [str(item_one), str(item_two)])
                self.assertEqual(package.json()["documents"][0]["capture_targets"], [
                    dict(field_id="observation", slot_id="photo", repeat_item_id=str(item_two), required=True),
                ])
                reservation_path = path + "/capture-reservations"
                for bad_target in (str(item_one), None):
                    bad = await client.post(reservation_path, json=capture | {"repeat_item_id": bad_target},
                                            headers=headers)
                    self.assertEqual((bad.status_code, bad.json()["detail"]), (422, "INVALID_CAPTURE_BINDING"))
                first = await client.post(reservation_path, json=capture, headers=headers)
                self.assertEqual(first.status_code, 201, first.text)
                repeat = await client.post(reservation_path, json=capture, headers=headers)
                self.assertEqual(repeat.status_code, 200)
                self.assertEqual(repeat.json(), first.json() | {"replayed": True})
                conflict = await client.post(reservation_path, json=capture | {"digest": "b" * 64},
                                             headers=headers)
                self.assertEqual((conflict.status_code, conflict.json()["detail"]),
                                 (409, "IDEMPOTENCY_PAYLOAD_MISMATCH"))
                stored_id = UUID(first.json()["reservation_id"])
                staged_reservations.add(stored_id)
                original_path = reservation_path + f"/{stored_id}/original"
                oversized = await client.put(original_path, params=scope, content=original + b"x", headers=headers)
                self.assertEqual(oversized.status_code, 413)
                uploaded = await client.put(original_path, params=scope, content=original, headers=headers)
                self.assertEqual(uploaded.status_code, 200, uploaded.text)
                repeat_upload = await client.put(original_path, params=scope, content=original, headers=headers)
                self.assertEqual(repeat_upload.json(), uploaded.json())
                alternative = b"z" * len(original)
                if cloud_fixture is None:
                    with self.assertRaises(HTTPException) as overwrite:
                        await disk.store_original(
                            stored_id, alternative, expected_digest=sha256(alternative).hexdigest(),
                            expected_length=len(alternative), deadline=datetime.now(timezone.utc) + timedelta(minutes=1),
                        )
                    self.assertEqual(overwrite.exception.detail, "INSPECTION_ORIGINAL_CONFLICT")
                durable = await staged_storage().read_original(stored_id)
                self.assertEqual(durable.backend_id, cloud_fixture.backend_id if cloud_fixture else permanent.backend_id)
                self.assertEqual(durable.received_at.isoformat(), uploaded.json()["received_at"].replace("Z", "+00:00"))
                self.assertEqual(durable.content, original)
                finalize_path = reservation_path + "/" + first.json()["reservation_id"] + "/finalize"
                finalize = capture | {"key_id": str(key_id), "signature": signature}
                missing_timestamp.add(stored_id)
                rejected = await client.post(finalize_path, json=finalize, headers=headers)
                self.assertEqual((rejected.status_code, rejected.json()["detail"]),
                                 (503, "INSPECTION_STORAGE_RECEIPT_INVALID"))
                async with sessions() as db:
                    self.assertEqual(await db.scalar(text("""
                        SELECT count(*) FROM evidence WHERE vendor_id = :vendor_id
                    """), ids), 0)
                    self.assertEqual(await db.scalar(text("""
                        SELECT count(*) FROM inspection_capture_receipt WHERE reservation_id = :id
                    """), {"id": stored_id}), 0)
                missing_timestamp.remove(stored_id)

                async with sessions.begin() as db:
                    await db.execute(text("""
                        CREATE FUNCTION fail_fixture_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
                        BEGIN
                            RAISE EXCEPTION 'synthetic failure after evidence flush';
                        END
                        $$
                    """))
                    await db.execute(text("""
                        CREATE TRIGGER fail_fixture_receipt BEFORE INSERT ON inspection_capture_receipt
                        FOR EACH ROW EXECUTE FUNCTION fail_fixture_receipt()
                    """))
                async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False),
                                       base_url="http://test") as failing:
                    failed = await failing.post(finalize_path, json=finalize, headers=headers)
                    self.assertEqual(failed.status_code, 500)
                async with sessions.begin() as db:
                    self.assertEqual(await db.scalar(text("""
                        SELECT count(*) FROM evidence WHERE vendor_id = :vendor_id
                    """), ids), 0)
                    self.assertEqual(await db.scalar(text("""
                        SELECT count(*) FROM inspection_capture_receipt WHERE reservation_id = :id
                    """), {"id": UUID(first.json()["reservation_id"])}), 0)
                    await db.execute(text("DROP TRIGGER fail_fixture_receipt ON inspection_capture_receipt"))
                    await db.execute(text("DROP FUNCTION fail_fixture_receipt()"))

                async def drop_response(scope, receive, send):
                    async def dropped(message):
                        if message["type"] == "http.response.start" and message["status"] == 201:
                            if scope["path"] == finalize_path:
                                self.assertEqual(await staging.purge_finalized(older_than_seconds=0), 1)
                                staging_purged.set()
                            raise ReadError("synthetic response loss after commit")
                        await send(message)
                    await app(scope, receive, dropped)

                parallel_reservation = UUID(first.json()["reservation_id"])
                async with AsyncClient(transport=ASGITransport(app=drop_response),
                                       base_url="http://test") as lossy:
                    outcomes = await asyncio.gather(
                        lossy.post(finalize_path, json=finalize, headers=headers),
                        lossy.post(finalize_path, json=finalize, headers=headers),
                        return_exceptions=True,
                    )
                    self.assertEqual(sum(isinstance(result, ReadError) for result in outcomes), 1)
                    self.assertEqual([result.status_code for result in outcomes if not isinstance(result, Exception)],
                                     [200])
                replay = await client.post(finalize_path, json=finalize, headers=headers)
                self.assertEqual(replay.status_code, 200, replay.text)
                self.assertTrue(replay.json()["replayed"])
                self.assertEqual([result.json() for result in outcomes if not isinstance(result, Exception)],
                                 [replay.json()])
                self.assertEqual(replay.json()["received_at"], uploaded.json()["received_at"])
                self.assertTrue(staging_purged.is_set())
                self.assertEqual(replay.json()["repeat_item_id"], str(item_two))
                self.assertEqual(len(reads), 4)
                changed = await client.post(finalize_path, json=finalize | {"signature": "modified"}, headers=headers)
                self.assertEqual((changed.status_code, changed.json()["detail"]),
                                 (409, "IDEMPOTENCY_PAYLOAD_MISMATCH"))
                accepted_visit, accepted_assignment, accepted_document = (uuid4() for _ in range(3))
                invalid_visit, invalid_assignment, invalid_document = (uuid4() for _ in range(3))
                invalid_workflow, invalid_requirement = uuid4(), uuid4()
                async with sessions.begin() as db:
                    await db.execute(text("""
                        INSERT INTO inspection_workflow_version (id, tenant_id, owner_client_id)
                        VALUES (:workflow, :tenant_id, :owner_client_id)
                    """), ids | {"workflow": invalid_workflow})
                    await db.execute(text("""
                        INSERT INTO inspection_document_requirement (
                            id, workflow_version_id, tenant_id, owner_client_id, form_version_id,
                            position, min_instances, max_instances, activation_condition
                        ) VALUES (:requirement, :workflow, :tenant_id, :owner_client_id, :form, 1, 1, 1,
                                  CAST(:condition AS jsonb))
                    """), ids | {"workflow": invalid_workflow, "requirement": invalid_requirement, "form": form,
                                 "condition": json.dumps({"field": "synthetic", "equals": True})})
                    await db.execute(text("""
                        UPDATE inspection_workflow_version SET published_at = clock_timestamp()
                        WHERE id = :workflow
                    """), {"workflow": invalid_workflow})
                    for v_id, a_id, d_id, wf_id, req_id in (
                        (accepted_visit, accepted_assignment, accepted_document, workflow, requirement),
                        (invalid_visit, invalid_assignment, invalid_document, invalid_workflow, invalid_requirement),
                    ):
                        fixture = ids | dict(visit_id=v_id, assignment_id=a_id,
                                             workflow=wf_id, document=d_id, requirement=req_id, form=form)
                        await db.execute(text("""
                            INSERT INTO inspection_visit
                                (id, tenant_id, owner_client_id, vendor_id, expires_at,
                                 assignment_id, workflow_version_id)
                            VALUES (:visit_id, :tenant_id, :owner_client_id, :vendor_id,
                                    clock_timestamp() + interval '1 hour', :assignment_id, :workflow)
                        """), fixture)
                        await db.execute(text("""
                            INSERT INTO inspection_document_instance
                                (id, visit_id, tenant_id, owner_client_id, form_version_id, ordinal,
                                 workflow_version_id, requirement_id, instance_number)
                            VALUES (:document, :visit_id, :tenant_id, :owner_client_id, :form, 1,
                                    :workflow, :requirement, 1)
                        """), fixture)
                        await db.execute(text("""
                            INSERT INTO inspection_capture_target
                                (id, document_instance_id, visit_id, field_id, slot_id, repeat_item_id, required)
                            VALUES (:target, :document, :visit_id, 'observation', 'photo', :item, true)
                        """), fixture | {"target": uuid4(), "item": item_two})
                        await db.execute(text("""
                            UPDATE inspection_visit SET package_sealed_at = clock_timestamp() WHERE id = :visit_id
                        """), fixture)

                invalid_path = f"/api/inspection-visits/{invalid_visit}"
                invalid_scope = scope | {"assignment_id": str(invalid_assignment)}
                invalid_pkg = await client.get(invalid_path + "/package", params=invalid_scope, headers=headers)
                self.assertEqual(invalid_pkg.json()["code"], "PACKAGE_UNSUPPORTED")
                self.assertEqual(len(invalid_pkg.json()["documents"]), 1)
                invalid_capture = capture | invalid_scope | {"document_instance_id": str(invalid_document)}
                denied = await client.post(invalid_path + "/capture-reservations",
                                           json=invalid_capture, headers=headers)
                self.assertEqual((denied.status_code, denied.json()["detail"]),
                                 (409, "UNSUPPORTED_VISIT_DOCUMENT_CONFIGURATION"))

                accepted_key = uuid4()
                async with sessions.begin() as db:
                    db.add(DeviceKey(
                        key_id=accepted_key, tenant_id=ids["tenant_id"], vendor_id=vendor_id,
                        public_key=pem, key_fingerprint=compute_key_fingerprint(pem),
                        inspection_enrollment_id=uuid4(),
                    ))
                accepted_path = f"/api/inspection-visits/{accepted_visit}/capture-reservations"
                accepted_capture = capture | {"assignment_id": str(accepted_assignment),
                                              "document_instance_id": str(accepted_document)}
                reserved = await client.post(accepted_path, json=accepted_capture, headers=headers)
                self.assertEqual(reserved.status_code, 201, reserved.text)
                accepted_finalize_path = accepted_path + "/" + reserved.json()["reservation_id"] + "/finalize"
                accepted_body = accepted_capture | {"key_id": str(accepted_key), "signature": signature}
                accepted = await client.post(accepted_finalize_path, json=accepted_body, headers=headers)
                self.assertEqual(accepted.status_code, 201, accepted.text)
                document_answers = {
                    "document_instance_id": str(accepted_document),
                    "repeat_items": [
                        {"repeat_item_id": str(item_one), "answers": {"measurement": {"value": "1.25", "scale": 2, "unit": "mm"}}},
                        {"repeat_item_id": str(item_two), "answers": {"measurement": {"value": "2.50", "scale": 2, "unit": "mm"}}},
                    ],
                    "evidence": [{
                        "repeat_item_id": str(item_two), "field_id": "observation", "slot_id": "photo",
                        "evidence_id": accepted.json()["evidence_id"],
                    }],
                }
                submit_path = f"/api/inspection-visits/{accepted_visit}/submit"
                submit_body = scope | {
                    "assignment_id": str(accepted_assignment), "submit_key": "snapshot-1",
                    "expected_revision": 0, "documents": [document_answers],
                }
                wrong_slot = document_answers | {"evidence": [
                    document_answers["evidence"][0] | {"repeat_item_id": str(item_one)},
                ]}
                for invalid_body, expected in (
                    (submit_body | {"generation": 2}, (409, "ASSIGNMENT_GENERATION_STALE")),
                    (submit_body | {"documents": [wrong_slot]}, (422, "INVALID_CAPTURE_BINDING")),
                    (submit_body | {"expected_revision": 1}, (409, "VISIT_REVISION_CONFLICT")),
                    (submit_body | {"documents": []}, (422, "INVALID_DOCUMENT_INSTANCE_SET")),
                ):
                    rejected = await client.post(submit_path, json=invalid_body, headers=headers)
                    self.assertEqual((rejected.status_code, rejected.json()["detail"]), expected)
                async with sessions() as db:
                    for table in ("inspection_visit_submission", "inspection_document_revision",
                                  "inspection_submission_document"):
                        self.assertEqual(await db.scalar(text(f"""
                            SELECT count(*) FROM {table} WHERE visit_id = :visit
                        """), {"visit": accepted_visit}), 0)
                async with sessions() as db:
                    await db.execute(text("SET LOCAL ROLE gate1_submit_runtime"))
                    await db.execute(text("""
                        INSERT INTO inspection_visit_submission (
                            id, visit_id, assignment_id, generation, submit_key, request_digest,
                            manifest, manifest_digest, submitted_at, accepted_revision
                        ) VALUES (:id, :visit, :assignment, 1, 'unsealed', 'x',
                                  '{}', 'x', clock_timestamp(), 1)
                    """), {"id": uuid4(), "visit": accepted_visit, "assignment": accepted_assignment})
                    with self.assertRaises(DBAPIError) as unsealed:
                        await db.commit()
                    self.assertEqual(unsealed.exception.orig.sqlstate, "55000")

                async with sessions.begin() as db:
                    await db.execute(text("""
                        CREATE FUNCTION fixture_fail_submission() RETURNS trigger LANGUAGE plpgsql AS $$
                        BEGIN
                            RAISE EXCEPTION 'synthetic failure after revision insertion';
                        END;
                        $$
                    """))
                    await db.execute(text("""
                        CREATE TRIGGER fixture_fail_submission BEFORE INSERT ON inspection_submission_document
                        FOR EACH ROW EXECUTE FUNCTION fixture_fail_submission()
                    """))
                async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False),
                                       base_url="http://test") as failing:
                    failed = await failing.post(submit_path, json=submit_body, headers=headers)
                    self.assertEqual(failed.status_code, 500)
                async with sessions.begin() as db:
                    self.assertEqual(tuple((await db.execute(text("""
                        SELECT revision, submitted_at FROM inspection_visit WHERE id = :visit
                    """), {"visit": accepted_visit})).one()), (0, None))
                    for table in ("inspection_visit_submission", "inspection_document_revision",
                                  "inspection_submission_document"):
                        self.assertEqual(await db.scalar(text(f"""
                            SELECT count(*) FROM {table} WHERE visit_id = :visit
                        """), {"visit": accepted_visit}), 0)
                    await db.execute(text("DROP TRIGGER fixture_fail_submission ON inspection_submission_document"))
                    await db.execute(text("DROP FUNCTION fixture_fail_submission()"))
                    await db.execute(text("""
                        CREATE FUNCTION fixture_pause_submission() RETURNS trigger LANGUAGE plpgsql AS $$
                        BEGIN
                            PERFORM pg_advisory_xact_lock(732149);
                            RETURN NEW;
                        END;
                        $$
                    """))
                    await db.execute(text("""
                        CREATE TRIGGER fixture_pause_submission BEFORE INSERT ON inspection_submission_document
                        FOR EACH ROW EXECUTE FUNCTION fixture_pause_submission()
                    """))

                async def wait_for_endpoint_blocked(observer, blocker):
                    for _ in range(100):
                        await observer.execute(text("SELECT pg_stat_clear_snapshot()"))
                        waiter = await observer.scalar(text("""
                            SELECT a.pid FROM pg_stat_activity AS a
                            WHERE a.datname = current_database() AND :blocker = ANY(pg_blocking_pids(a.pid))
                            LIMIT 1
                        """), {"blocker": blocker})
                        if waiter:
                            return waiter
                        await asyncio.sleep(0.03)
                    self.fail("Expected the endpoint transaction to block")

                async with AsyncClient(transport=ASGITransport(app=drop_response),
                                       base_url="http://test") as lossy:
                    async with sessions() as barrier, sessions() as revoker, sessions() as observer:
                        barrier_pid = await barrier.scalar(text("SELECT pg_backend_pid()"))
                        await barrier.execute(text("SELECT pg_advisory_xact_lock(732149)"))
                        requests = []
                        try:
                            primary = asyncio.create_task(lossy.post(submit_path, json=submit_body, headers=headers))
                            requests.append(primary)
                            submit_pid = await wait_for_endpoint_blocked(observer, barrier_pid)
                            revoker_pid = await revoker.scalar(text("SELECT pg_backend_pid()"))
                            revocation = asyncio.create_task(revoke_inspection_key(
                                revoker, tenant_id=ids["tenant_id"], vendor_id=vendor_id, key_id=accepted_key,
                            ))
                            requests.append(revocation)
                            await wait_for_lock(observer, revoker_pid, submit_pid)
                            second = asyncio.create_task(client.post(
                                submit_path, json=submit_body | {"submit_key": "other-key"}, headers=headers,
                            ))
                            requests.append(second)
                            await barrier.commit()
                            with self.assertRaises(ReadError):
                                await asyncio.wait_for(primary, 5)
                            await asyncio.wait_for(revocation, 5)
                            await revoker.commit()
                            losing_submit = await asyncio.wait_for(second, 5)
                            self.assertEqual((losing_submit.status_code, losing_submit.json()["detail"]),
                                             (409, "VISIT_ALREADY_SUBMITTED"))
                        finally:
                            for task in requests:
                                if not task.done():
                                    task.cancel()
                            await asyncio.gather(*requests, return_exceptions=True)
                async with sessions.begin() as db:
                    await db.execute(text("DROP TRIGGER fixture_pause_submission ON inspection_submission_document"))
                    await db.execute(text("DROP FUNCTION fixture_pause_submission()"))
                submitted = await client.post(submit_path, json=submit_body, headers=headers)
                self.assertEqual(submitted.status_code, 201, submitted.text)
                self.assertTrue(submitted.json()["replayed"])
                self.assertEqual(submitted.json()["accepted_revision"], 1)
                self.assertEqual(len(submitted.json()["documents"]), 1)
                conflict = await client.post(submit_path, json=submit_body | {"expected_revision": 1},
                                             headers=headers)
                self.assertEqual((conflict.status_code, conflict.json()["detail"]),
                                 (409, "IDEMPOTENCY_PAYLOAD_MISMATCH"))
                async with sessions() as db:
                    row = (await db.execute(text("""
                        SELECT s.id, s.sealed, s.manifest_digest, s.manifest, d.id AS revision_id, d.content,
                               d.digest AS revision_digest, v.revision

                        FROM inspection_visit_submission AS s
                        JOIN inspection_visit AS v ON v.id = s.visit_id
                        JOIN inspection_submission_document AS m ON m.submission_id = s.id
                        JOIN inspection_document_revision AS d ON d.id = m.revision_id
                        WHERE s.visit_id = :visit
                    """), {"visit": accepted_visit})).mappings().one()
                    self.assertEqual(str(row["id"]), submitted.json()["submission_id"])
                    self.assertEqual(str(row["revision_id"]), submitted.json()["documents"][0]["revision_id"])
                    self.assertTrue(row["sealed"])
                    self.assertEqual(row["revision"], 1)
                    self.assertEqual(row["manifest_digest"], submitted.json()["manifest_digest"])
                    self.assertEqual(sha256(row["manifest"].encode()).hexdigest(), row["manifest_digest"])
                    self.assertEqual(sha256(row["content"].encode()).hexdigest(), row["revision_digest"])
                    self.assertEqual(json.loads(row["content"])["evidence"][0]["repeat_item_id"], str(item_two))
                    sealed_id = row["id"]
                for sql, sqlstate in (
                    ("UPDATE inspection_visit_submission SET sealed = false WHERE id = :id", "55000"),
                    ("DELETE FROM inspection_visit_submission WHERE id = :id", "42501"),
                    ("TRUNCATE inspection_visit_submission CASCADE", "42501"),
                    ("DELETE FROM inspection_visit WHERE id = :visit", "42501"),
                    ("UPDATE inspection_document_revision SET digest = 'tampered' WHERE id = :revision", "42501"),
                    ("ALTER TABLE inspection_visit_submission DISABLE TRIGGER ALL", "42501"),
                    ("""INSERT INTO inspection_submission_document
                        SELECT submission_id, document_instance_id, visit_id, revision_id, ordinal
                        FROM inspection_submission_document WHERE submission_id = :id""", "55000"),
                ):
                    async with sessions() as db:
                        await db.execute(text("SET LOCAL ROLE gate1_submit_runtime"))
                        with self.assertRaises(DBAPIError) as immutable:
                            await db.execute(text(sql), {
                                "id": sealed_id, "visit": accepted_visit,
                                "revision": UUID(submitted.json()["documents"][0]["revision_id"]),
                            })
                        self.assertEqual(immutable.exception.orig.sqlstate, sqlstate)
                for sql, params in (
                    ("DELETE FROM clients WHERE client_id = :id", {"id": ids["owner_client_id"]}),
                    ("DELETE FROM vendors WHERE vendor_id = :id", {"id": vendor_id}),
                    ("DELETE FROM evidence WHERE evidence_id = :id", {
                        "id": UUID(accepted.json()["evidence_id"]),
                    }),
                ):
                    async with sessions() as db:
                        with self.assertRaises(IntegrityError) as restricted:
                            await db.execute(text(sql), params)
                        self.assertIn(restricted.exception.orig.sqlstate, ("23001", "23503"))
                reads_before = len(reads)
                settled = await client.post(accepted_finalize_path, json=accepted_body, headers=headers)
                self.assertEqual(settled.status_code, 200, settled.text)
                self.assertEqual(settled.json(), accepted.json() | {
                    "replayed": True, "eligible": False, "eligibility_reason": "EVIDENCE_KEY_REVOKED",
                })
                self.assertEqual(len(reads), reads_before)
                async with sessions() as db:
                    self.assertEqual(await db.scalar(text("""
                        SELECT count(*) FROM inspection_capture_receipt AS c
                        JOIN inspection_upload_reservation AS r ON r.id = c.reservation_id
                        WHERE r.visit_id = :visit
                    """), {"visit": accepted_visit}), 1)

                short_finalized_id = uuid4()
                short_capture = capture | {
                    "upload_key": "short-finalized", "client_capture_id": str(uuid4()),
                }
                async with sessions.begin() as db:
                    await db.execute(text("""
                        INSERT INTO inspection_upload_reservation (
                            id, visit_id, assignment_id, generation, target_id, client_capture_id,
                            upload_key, digest, byte_length, deadline
                        ) VALUES (
                            :id, :visit_id, :assignment_id, 1, :target, :capture_id,
                            :upload_key, :digest, :byte_length, clock_timestamp() + interval '2 seconds'
                        )
                    """), ids | short_capture | {
                        "id": short_finalized_id, "target": target, "assignment_id": ids["assignment_id"],
                        "capture_id": UUID(short_capture["client_capture_id"]),
                    })
                disk_reservations.add(short_finalized_id)
                short_url = reservation_path + f"/{short_finalized_id}"
                uploaded_short = await client.put(short_url + "/original", params=scope, content=original,
                                                  headers=headers)
                self.assertEqual(uploaded_short.status_code, 200, uploaded_short.text)
                short_result = await client.post(
                    short_url + "/finalize",
                    json=short_capture | {"key_id": str(key_id), "signature": signature}, headers=headers,
                )
                self.assertEqual(short_result.status_code, 201, short_result.text)

                late_id = uuid4()
                late_capture = capture | {"upload_key": "short-deadline", "client_capture_id": str(uuid4())}
                async with sessions.begin() as db:
                    await db.execute(text("""
                        INSERT INTO inspection_upload_reservation (
                            id, visit_id, assignment_id, generation, target_id, client_capture_id,
                            upload_key, digest, byte_length, deadline
                        ) VALUES (
                            :id, :visit_id, :assignment_id, 1, :target, :capture_id,
                            :upload_key, :digest, :byte_length, clock_timestamp() + interval '2 seconds'
                        )
                    """), ids | late_capture | {
                        "id": late_id, "target": target, "assignment_id": ids["assignment_id"],
                        "capture_id": UUID(late_capture["client_capture_id"]),
                    })

                from app.services.inspection_storage_cleanup import sweep_inspection_originals

                local_cleanup = StagedInspectionStorage(staging, {permanent.backend_id: permanent}, permanent.backend_id, max_bytes=1024)
                disk_reservations.add(late_id)
                await local_cleanup.store_original(
                    late_id, original, expected_digest=digest, expected_length=len(original),
                    deadline=datetime.now(timezone.utc) + timedelta(seconds=2),
                )

                async def expire_reservation_during_read():
                    await asyncio.sleep(2)

                before_read[late_id] = expire_reservation_during_read
                late = await client.post(
                    reservation_path + f"/{late_id}/finalize",
                    json=late_capture | {"key_id": str(key_id), "signature": signature},
                    headers=headers,
                )
                self.assertEqual((late.status_code, late.json()["detail"]), (410, "VISIT_EXPIRED"))
                never_staged = uuid4()
                async with sessions.begin() as db:
                    await db.execute(text("""
                        INSERT INTO inspection_upload_reservation (
                            id, visit_id, assignment_id, generation, target_id, client_capture_id,
                            upload_key, digest, byte_length, deadline
                        )
                        SELECT :new_id, visit_id, assignment_id, generation, target_id, :capture_id,
                               'expired-without-receipt', digest, byte_length, deadline
                        FROM inspection_upload_reservation WHERE id = :old_id
                    """), {"new_id": never_staged, "capture_id": uuid4(), "old_id": late_id})
                with self.assertRaises(HTTPException) as expired_stage:
                    await staging.accept(never_staged, original, permanent.backend_id)
                self.assertEqual((expired_stage.exception.status_code, expired_stage.exception.detail),
                                 (410, "VISIT_EXPIRED"))
                self.assertNotIn(late_id, before_read)
                self.assertEqual(await sweep_inspection_originals(sessions, local_cleanup), (None, []))
                self.assertEqual(await sweep_inspection_originals(sessions, local_cleanup), (None, []))
                self.assertEqual(await staging.backend_for(late_id), permanent.backend_id)
                with self.assertRaises(HTTPException):
                    await staging.read(late_id)
                with self.assertRaises(HTTPException) as late_write:
                    await disk.store_original(
                        late_id, original, expected_digest=digest, expected_length=len(original),
                        deadline=datetime.now(timezone.utc) + timedelta(minutes=1),
                    )
                self.assertEqual(late_write.exception.detail, "CAPTURE_RESERVATION_ABANDONED")
                self.assertFalse((Path(directory.name) / str(late_id) / "original").exists())
                async with sessions() as db:
                    self.assertTrue(await db.scalar(text("""
                        SELECT deadline < clock_timestamp() FROM inspection_upload_reservation WHERE id = :id
                    """), {"id": short_finalized_id}))
                    self.assertFalse(await clean_expired_inspection_original(
                        db, reservation_id=short_finalized_id, storage=disk,
                    ))
                self.assertEqual((await disk.read_original(short_finalized_id)).content, original)
                async with sessions() as db:
                    self.assertFalse(await clean_expired_inspection_original(db, reservation_id=stored_id, storage=disk))
                self.assertTrue(staging_purged.is_set())
                with self.assertRaises(HTTPException) as purged:
                    await staging.read(stored_id)
                self.assertEqual(purged.exception.detail, "CAPTURE_ORIGINAL_NOT_STORED")
                self.assertEqual(await staging.backend_for(stored_id), durable.backend_id)
                new_location_dir = TemporaryDirectory()
                self.addCleanup(new_location_dir.cleanup)
                new_location = LocalPermanentOriginalStore(Path(new_location_dir.name))
                self.assertNotEqual(new_location.backend_id, permanent.backend_id)
                configured_stores = {permanent.backend_id: permanent, new_location.backend_id: new_location}
                if cloud_fixture is not None:
                    configured_stores[cloud_fixture.backend_id] = cloud_fixture
                switched = StagedInspectionStorage(
                    staging, configured_stores, new_location.backend_id, max_bytes=1024,
                )
                fixture_dependency = app.dependency_overrides[get_inspection_original_storage]
                app.dependency_overrides[get_inspection_original_storage] = lambda: switched
                try:
                    photo_path = path + "/evidence/" + replay.json()["evidence_id"] + "/original"
                    read = await client.get(photo_path, params=scope, headers=headers)
                    self.assertEqual(read.status_code, 200, read.text)
                    self.assertEqual(read.content, original)
                    self.assertEqual(read.headers["cache-control"], "private, no-store")
                    denied = await client.get(photo_path, params=scope | {"owner_client_id": str(uuid4())},
                                              headers=headers)
                    self.assertEqual(denied.status_code, 404)
                    new_capture = capture | {"upload_key": "new-location", "client_capture_id": str(uuid4())}
                    new_reservation = await client.post(reservation_path, json=new_capture, headers=headers)
                    self.assertEqual(new_reservation.status_code, 201, new_reservation.text)
                    new_reservation_id = UUID(new_reservation.json()["reservation_id"])
                    uploaded_to_new = await client.put(
                        reservation_path + f"/{new_reservation_id}/original",
                        params=scope, content=original, headers=headers,
                    )
                    self.assertEqual(uploaded_to_new.status_code, 200, uploaded_to_new.text)
                    self.assertEqual(await staging.backend_for(new_reservation_id), new_location.backend_id)
                    self.assertEqual(await new_location.retrieve(new_reservation_id, limit=len(original)), original)
                    app.dependency_overrides[get_inspection_original_storage] = lambda: StagedInspectionStorage(
                        staging, {new_location.backend_id: new_location}, new_location.backend_id, max_bytes=1024,
                    )
                    missing_location = await client.get(photo_path, params=scope, headers=headers)
                    self.assertEqual(missing_location.status_code, 503)
                finally:
                    app.dependency_overrides[get_inspection_original_storage] = fixture_dependency

                async with sessions.begin() as db:
                    await db.execute(text("""
                        CREATE FUNCTION fixture_delay_stage_commit() RETURNS trigger LANGUAGE plpgsql AS $$
                        DECLARE cutoff timestamptz; operation text;
                        BEGIN
                            SELECT deadline, upload_key INTO cutoff, operation
                            FROM inspection_upload_reservation WHERE id = NEW.reservation_id;
                            IF operation IN ('deadline-commit', 'deadline-rollback') THEN
                                PERFORM pg_sleep(greatest(0, extract(epoch FROM cutoff - clock_timestamp())) + 0.05);
                                IF operation = 'deadline-rollback' THEN
                                    RAISE EXCEPTION 'synthetic commit-path failure';
                                END IF;
                            END IF;
                            RETURN NULL;
                        END;
                        $$
                    """))
                    await db.execute(text("""
                        CREATE CONSTRAINT TRIGGER fixture_delay_stage_commit
                        AFTER INSERT ON inspection_original_staging DEFERRABLE INITIALLY DEFERRED
                        FOR EACH ROW EXECUTE FUNCTION fixture_delay_stage_commit()
                    """))
                for operation in ("deadline-commit", "deadline-rollback"):
                    staged_id = uuid4()
                    async with sessions.begin() as db:
                        cutoff = await db.scalar(text("""
                            INSERT INTO inspection_upload_reservation (
                                id, visit_id, assignment_id, generation, target_id, client_capture_id,
                                upload_key, digest, byte_length, deadline
                            ) VALUES (
                                :id, :visit_id, :assignment_id, 1, :target, :capture_id, :key, :digest,
                                :byte_length, clock_timestamp() + interval '1 second'
                            ) RETURNING deadline
                        """), ids | dict(id=staged_id, target=target, capture_id=uuid4(), key=operation,
                                        digest=digest, byte_length=len(original)))
                    if operation == "deadline-commit":
                        admitted = await staging.accept(staged_id, original, new_location.backend_id)
                        self.assertLessEqual(admitted.received_at, cutoff)
                        self.assertEqual(await staging.read(staged_id), admitted)
                        async with sessions() as db:
                            self.assertGreater(await db.scalar(text("SELECT clock_timestamp()")), cutoff)
                    else:
                        with self.assertRaises(DBAPIError):
                            await staging.accept(staged_id, original, new_location.backend_id)
                        with self.assertRaises(HTTPException) as unstaged:
                            await staging.read(staged_id)
                        self.assertEqual(unstaged.exception.detail, "CAPTURE_ORIGINAL_NOT_STORED")
                        with self.assertRaises(HTTPException) as too_late:
                            await staging.accept(staged_id, original, new_location.backend_id)
                        self.assertEqual((too_late.exception.status_code, too_late.exception.detail),
                                         (410, "VISIT_EXPIRED"))
                async with sessions.begin() as db:
                    await db.execute(text("DROP TRIGGER fixture_delay_stage_commit ON inspection_original_staging"))
                    await db.execute(text("DROP FUNCTION fixture_delay_stage_commit()"))

                async with sessions.begin() as db:
                    await db.execute(update(DeviceKey).where(DeviceKey.key_id == key_id).values(
                        active_to=text("clock_timestamp()"),
                    ))
                rotated = await client.post(finalize_path, json=finalize, headers=headers)
                self.assertEqual(rotated.status_code, 200)
                self.assertTrue(rotated.json()["eligible"])
                retired_capture = capture | {"upload_key": "retired-key", "client_capture_id": str(uuid4())}
                reserved = await client.post(reservation_path, json=retired_capture, headers=headers)
                self.assertEqual(reserved.status_code, 201, reserved.text)
                retired = await client.post(
                    reservation_path + "/" + reserved.json()["reservation_id"] + "/finalize",
                    json=retired_capture | {"key_id": str(key_id), "signature": signature}, headers=headers,
                )
                self.assertEqual((retired.status_code, retired.json()["detail"]),
                                 (422, "CAPTURE_KEY_INELIGIBLE"))

                pending_doc = document_answers | {
                    "document_instance_id": str(document),
                    "evidence": [document_answers["evidence"][0] | {
                        "evidence_id": replay.json()["evidence_id"],
                    }],
                }
                revoked_submit = None

                async def revoke_during_transfer():
                    nonlocal revoked_submit
                    async with sessions() as db, sessions() as observer:
                        blocker = await db.scalar(text("SELECT pg_backend_pid()"))
                        await revoke_inspection_key(
                            db, tenant_id=ids["tenant_id"], vendor_id=vendor_id, key_id=key_id,
                        )
                        await db.flush()
                        pending = asyncio.create_task(client.post(
                            path + "/submit",
                            json=submit_body | scope | {"documents": [pending_doc]}, headers=headers,
                        ))
                        try:
                            await wait_for_endpoint_blocked(observer, blocker)
                            await db.commit()
                            revoked_submit = await asyncio.wait_for(pending, 5)
                        finally:
                            if not pending.done():
                                pending.cancel()
                                await asyncio.gather(pending, return_exceptions=True)

                new_capture = capture | {"upload_key": "revoke-during-transfer",
                                         "client_capture_id": str(uuid4())}
                reserved = await client.post(reservation_path, json=new_capture, headers=headers)
                held_id = UUID(reserved.json()["reservation_id"])
                before_read[held_id] = revoke_during_transfer
                denied = await client.post(
                    reservation_path + f"/{held_id}/finalize",
                    json=new_capture | {"key_id": str(key_id), "signature": signature}, headers=headers,
                )
                self.assertEqual((denied.status_code, denied.json()["detail"]), (422, "EVIDENCE_KEY_REVOKED"))
                revoked_replay = await client.post(finalize_path, json=finalize, headers=headers)
                self.assertEqual(revoked_replay.status_code, 200)
                self.assertEqual(revoked_replay.json()["evidence_id"], replay.json()["evidence_id"])
                self.assertEqual(revoked_replay.json()["eligibility_reason"], "EVIDENCE_KEY_REVOKED")
                self.assertEqual((revoked_submit.status_code, revoked_submit.json()["detail"]),
                                 (422, "EVIDENCE_KEY_REVOKED"))
                async with sessions() as db:
                    for table in ("inspection_visit_submission", "inspection_document_revision",
                                  "inspection_submission_document"):
                        self.assertEqual(await db.scalar(text(f"""
                            SELECT count(*) FROM {table} WHERE visit_id = :visit_id
                        """), ids), 0)

                replacement = "SHIFT1"
                async with sessions.begin() as db:
                    db.add(Vendor(
                        vendor_id=replacement, tenant_id=ids["tenant_id"],
                        created_by_client_id=ids["owner_client_id"], name="Replacement",
                        phone_number="+15550109999",
                    ))

                async def reassign_during_transfer():
                    owner_scope = {k: v for k, v in ids.items() if k != "vendor_id"}
                    async with sessions.begin() as db:
                        await reassign_visit(db, **owner_scope, new_vendor_id=replacement)

                moved_capture = capture | {"upload_key": "move-during-transfer",
                                           "client_capture_id": str(uuid4())}
                reserved = await client.post(reservation_path, json=moved_capture, headers=headers)
                moved_id = UUID(reserved.json()["reservation_id"])
                before_read[moved_id] = reassign_during_transfer
                original_read_path = path + "/evidence/" + replay.json()["evidence_id"] + "/original"
                pending_read = asyncio.create_task(client.get(original_read_path, params=scope, headers=headers))
                try:
                    await asyncio.wait_for(finalized_bytes_read.wait(), 5)
                    denied = await client.post(
                        reservation_path + f"/{moved_id}/finalize",
                        json=moved_capture | {"key_id": str(key_id), "signature": signature}, headers=headers,
                    )
                    self.assertEqual((denied.status_code, denied.json()["detail"]), (404, "VISIT_NOT_FOUND"))
                    self.assertFalse(pending_read.done())
                    release_finalized_read.set()
                    blocked_read = await asyncio.wait_for(pending_read, 5)
                    self.assertEqual((blocked_read.status_code, blocked_read.json()["detail"]),
                                     (404, "VISIT_NOT_FOUND"))
                    self.assertNotIn(original, blocked_read.content)
                finally:
                    release_finalized_read.set()
                    if not pending_read.done():
                        pending_read.cancel()
                        await asyncio.gather(pending_read, return_exceptions=True)

                async with sessions() as db:
                    current = await db.get(InspectionVisit, ids["visit_id"])
                    current_scope = scope | {"assignment_id": str(current.assignment_id),
                                             "generation": current.generation}
                    revocation_scope = dict(
                        tenant_id=ids["tenant_id"], owner_client_id=ids["owner_client_id"],
                        visit_id=ids["visit_id"], assignment_id=current.assignment_id,
                        generation=current.generation,
                    )
                replacement_token = create_access_token(dict(sub=replacement, type="vendor", vendor_id=replacement))
                replacement_headers = {"Authorization": f"Bearer {replacement_token}"}
                replacement_capture = capture | current_scope | {"client_capture_id": str(uuid4())}
                reserved = await client.post(reservation_path, json=replacement_capture,
                                             headers=replacement_headers)
                self.assertEqual(reserved.status_code, 201, reserved.text)
                replacement_id = UUID(reserved.json()["reservation_id"])

                async def revoke_visit_during_read():
                    async with sessions.begin() as db:
                        await revoke_visit(db, **revocation_scope)

                before_read[replacement_id] = revoke_visit_during_read
                denied = await client.post(
                    reservation_path + f"/{replacement_id}/finalize",
                    json=replacement_capture | {"key_id": str(key_id), "signature": signature},
                    headers=replacement_headers,
                )
                self.assertEqual((denied.status_code, denied.json()["detail"]), (403, "VISIT_REVOKED"))
            async with sessions() as db:
                rows = (await db.execute(text("""
                    SELECT r.id, t.repeat_item_id, c.id AS receipt_id, e.evidence_id
                    FROM inspection_upload_reservation AS r
                    JOIN inspection_capture_receipt AS c ON c.reservation_id = r.id
                    JOIN evidence AS e ON e.evidence_id = c.evidence_id
                    JOIN inspection_capture_target AS t ON t.id = r.target_id
                    WHERE r.visit_id = :visit_id AND r.upload_key <> 'short-finalized'
                """), ids)).all()
                self.assertEqual([(str(row.id), row.repeat_item_id, str(row.receipt_id), str(row.evidence_id))
                                  for row in rows], [
                    (first.json()["reservation_id"], item_two, replay.json()["receipt_id"],
                     replay.json()["evidence_id"]),
                ])
                self.assertEqual(await db.scalar(text("""
                    SELECT count(*) FROM evidence WHERE vendor_id = :vendor_id
                """), ids), 3)
        finally:
            await engine.dispose()

class InspectionCanonicalTests(unittest.TestCase):
    def test_rfc8785_restricted_profile(self):
        from app.services.inspection_submission import canonical_json, utc_timestamp

        fixture = {
            "\ufb33": "Hebrew", "\U0001f600": "Emoji", "\u20ac": "Euro",
            "timestamp": utc_timestamp(datetime(2026, 11, 24, 12, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))),
            "items": [{"value": "2.50", "unit": "mm", "scale": 2}, {"value": "1.25", "unit": "mm", "scale": 2}],
        }
        expected = (
            '{"items":[{"scale":2,"unit":"mm","value":"2.50"},{"scale":2,"unit":"mm","value":"1.25"}],'
            '"timestamp":"2026-11-24T07:00:00.000000Z","\u20ac":"Euro","\U0001f600":"Emoji","\ufb33":"Hebrew"}'
        )
        self.assertEqual(canonical_json(fixture).encode("utf-8"), expected.encode("utf-8"))
        self.assertNotEqual(canonical_json(fixture), canonical_json(fixture | {"items": fixture["items"][::-1]}))
        for invalid in ({"value": 0.1}, {"value": 9007199254740992}, {"value": "\ud800"}):
            with self.assertRaises(HTTPException):
                canonical_json(invalid)
