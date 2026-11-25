"""
Migrations 022-024 must converge from any starting state (M2 of the migration-drift repair).

Covers: vendor_tracks (adopt-not-recreate, catalog-driven constraint), api_keys, device_keys,
evidence signing columns, clients.report_settings, location_profiles geofence columns.

Migration 025 (REVIEW vendor seed) is NOT implemented in M2 — it requires a design decision.
"""
import importlib.util
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.hotfix_support import TEST_DATABASE_URL

BACKEND = Path(__file__).resolve().parents[1]
VERSIONS = BACKEND / "alembic" / "versions"
MIGRATIONS = ["022_vendor_tracks", "023_api_keys_device_keys", "024_schema_additions"]

# Columns M2 adds that were previously startup-only
EVIDENCE_SIGNING_COLS = {"signing_key_id", "signing_key_fingerprint", "signature_outcome"}
GEOFENCE_COLS = {"geofence_type", "viewport_ne_lat", "viewport_ne_lon", "viewport_sw_lat",
                 "viewport_sw_lon", "polygon_points", "corridor_buffer_meters", "geocode_accuracy"}


def _load(name):
    spec = importlib.util.spec_from_file_location(f"mig_{name}", VERSIONS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(conn, names=MIGRATIONS):
    ctx = MigrationContext.configure(conn)
    with Operations.context(ctx):
        for n in names:
            _load(n).upgrade()


def _q(conn, sql, **p):
    return conn.execute(text(sql), p)


STUBS = [
    "CREATE TABLE clients (client_id uuid PRIMARY KEY)",
    "CREATE TABLE campaigns (campaign_id uuid PRIMARY KEY)",
    "CREATE TABLE vendors (vendor_id varchar(6) PRIMARY KEY, tenant_id uuid, created_by_client_id uuid, name varchar(255), phone_number varchar(20), status varchar(20), device_verified boolean, created_at timestamptz, updated_at timestamptz)",
    "CREATE TABLE sensor_data (sensor_id uuid PRIMARY KEY)",
    "CREATE TABLE location_profiles (profile_id uuid PRIMARY KEY, campaign_id uuid NOT NULL UNIQUE)",
    "CREATE INDEX idx_location_profiles_campaign ON location_profiles (campaign_id)",
    "CREATE TABLE evidence (evidence_id uuid PRIMARY KEY, tenant_id uuid NOT NULL, vendor_id varchar(6), evidence_type varchar(20), verification_status varchar(20) DEFAULT 'pending', created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now(), metadata jsonb DEFAULT '{}', tags jsonb DEFAULT '[]', verification_flags jsonb DEFAULT '[]', sensor_data jsonb)",
    "CREATE TABLE cases (case_id uuid PRIMARY KEY)",
    "CREATE TABLE gps_tracks (track_id uuid PRIMARY KEY, evidence_id uuid)",
    "CREATE TABLE task_queue (id uuid PRIMARY KEY, status text)",
    "ALTER TABLE sensor_data ADD COLUMN accelerometer_data jsonb",
    "ALTER TABLE location_profiles ADD COLUMN asset_id varchar(100)",
    "ALTER TABLE location_profiles ADD COLUMN asset_type varchar(50)",
    "ALTER TABLE location_profiles ADD COLUMN location_description text",
    "ALTER TABLE location_profiles DROP CONSTRAINT location_profiles_campaign_id_key",
    "CREATE INDEX ix_location_profiles_campaign_id ON location_profiles (campaign_id)",
]


PROD_STATE = STUBS + [
    "CREATE TABLE IF NOT EXISTS vendor_tracks (track_id uuid PRIMARY KEY, tenant_id uuid NOT NULL, vendor_id varchar(6) NOT NULL, track_date date NOT NULL, points jsonb DEFAULT '[]', point_count integer DEFAULT 0, total_distance_meters float, start_time timestamptz, end_time timestamptz, duration_seconds float, status varchar(20) DEFAULT 'active', created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now(), UNIQUE(vendor_id, track_date))",
    "CREATE INDEX ix_vendor_tracks_vendor_date ON vendor_tracks (vendor_id, track_date)",
    "CREATE INDEX ix_vendor_tracks_tenant ON vendor_tracks (tenant_id)",
    "CREATE TABLE IF NOT EXISTS api_keys (key_id uuid PRIMARY KEY, client_id uuid, tenant_id uuid, key_hash varchar(255), key_prefix varchar(12), name varchar(100), permissions jsonb, rate_limit_per_minute integer, is_active boolean, last_used_at timestamptz, total_calls integer, created_at timestamptz)",
    "CREATE INDEX ix_api_keys_prefix ON api_keys (key_prefix)",
    "CREATE INDEX ix_api_keys_tenant ON api_keys (tenant_id)",
    "CREATE TABLE IF NOT EXISTS device_keys (key_id uuid PRIMARY KEY, vendor_id varchar(6), tenant_id uuid, device_id varchar(255), public_key text, algorithm varchar(50), key_fingerprint varchar(64), active_from timestamptz, active_to timestamptz, created_at timestamptz)",
    "CREATE INDEX ix_device_keys_vendor ON device_keys (vendor_id)",
    "CREATE INDEX ix_device_keys_fingerprint ON device_keys (key_fingerprint)",
    "CREATE INDEX ix_device_keys_vendor_window ON device_keys (vendor_id, active_from, active_to)",
    "ALTER TABLE evidence ADD COLUMN signing_key_id uuid",
    "ALTER TABLE evidence ADD COLUMN signing_key_fingerprint varchar(64)",
    "ALTER TABLE evidence ADD COLUMN signature_outcome varchar(30)",
    "ALTER TABLE clients ADD COLUMN report_settings jsonb",
    "ALTER TABLE location_profiles ADD COLUMN geofence_type varchar(20) DEFAULT 'circle'",
    "ALTER TABLE location_profiles ADD COLUMN viewport_ne_lat float",
    "ALTER TABLE location_profiles ADD COLUMN viewport_ne_lon float",
    "ALTER TABLE location_profiles ADD COLUMN viewport_sw_lat float",
    "ALTER TABLE location_profiles ADD COLUMN viewport_sw_lon float",
    "ALTER TABLE location_profiles ADD COLUMN polygon_points jsonb",
    "ALTER TABLE location_profiles ADD COLUMN corridor_buffer_meters float",
    "ALTER TABLE location_profiles ADD COLUMN geocode_accuracy varchar(20)",
    "INSERT INTO vendor_tracks (track_id, tenant_id, vendor_id, track_date, points, point_count, status, created_at, updated_at) VALUES (gen_random_uuid(), gen_random_uuid(), 'V00001', '2026-01-01', '[]', 0, 'active', now(), now())",
]


def _indexes(conn, schema):
    return {r[0] for r in _q(conn, "SELECT indexname FROM pg_indexes WHERE schemaname=:s", s=schema)}


def _cols(conn, schema, table):
    return {r[0] for r in _q(conn, "SELECT column_name FROM information_schema.columns WHERE table_schema=:s AND table_name=:t", s=schema, t=table)}


def _tables(conn, schema):
    return {r[0] for r in _q(conn, "SELECT tablename FROM pg_tables WHERE schemaname=:s", s=schema)}


def _unique_constraints_on(conn, schema, table):
    return {r[0] for r in _q(conn, "SELECT co.conname FROM pg_constraint co JOIN pg_class cl ON cl.oid=co.conrelid JOIN pg_namespace n ON n.oid=cl.relnamespace WHERE n.nspname=:s AND cl.relname=:t AND co.contype='u'", s=schema, t=table)}


async def _scratch(body, *, prod_state=False, extra_sql=()):
    import uuid as uuid_mod
    schema = "m2_" + uuid_mod.uuid4().hex[:10]
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.connect() as aconn:
            trans = await aconn.begin()
            try:
                def work(conn):
                    _q(conn, f'CREATE SCHEMA "{schema}"')
                    _q(conn, f'SET LOCAL search_path TO "{schema}", public')
                    for stmt in (STUBS if not prod_state else PROD_STATE) + list(extra_sql):
                        _q(conn, stmt)
                    return body(conn, schema)
                return await aconn.run_sync(work)
            finally:
                await trans.rollback()
    finally:
        await engine.dispose()


# ---- graph
def test_graph_is_chain_021_to_024():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["028_inspection_storage_fence"]
    expected = [("028_inspection_storage_fence", "027_inspection_submission"),
                ("027_inspection_submission", "026_inspection_capture"),
                ("026_inspection_capture", "025_gate1_visit_auth"),
                ("025_gate1_visit_auth", "024_schema_additions"),
                ("024_schema_additions", "023_api_keys_device_keys"),
                ("023_api_keys_device_keys", "022_vendor_tracks"),
                ("022_vendor_tracks", "021_evidence")]
    for rev, down in expected:
        assert script.get_revision(rev).down_revision == down


# ---- fresh install
@pytest.mark.asyncio
async def test_fresh_install_creates_all_objects():
    def body(conn, schema):
        _run(conn)
        tables = _tables(conn, schema)
        assert {"vendor_tracks", "api_keys", "device_keys"} <= tables
        assert EVIDENCE_SIGNING_COLS <= _cols(conn, schema, "evidence")
        assert "report_settings" in _cols(conn, schema, "clients")
        assert GEOFENCE_COLS <= _cols(conn, schema, "location_profiles")
        assert {"ix_vendor_tracks_vendor_date", "ix_vendor_tracks_tenant"} <= _indexes(conn, schema)
        assert {"ix_api_keys_prefix", "ix_api_keys_tenant"} <= _indexes(conn, schema)
        assert {"ix_device_keys_vendor", "ix_device_keys_fingerprint", "ix_device_keys_vendor_window"} <= _indexes(conn, schema)
        # unique constraint on vendor_tracks
        cons = _unique_constraints_on(conn, schema, "vendor_tracks")
        assert len(cons) == 1, f"expected 1 unique constraint, got {cons}"
    await _scratch(body)


# ---- production-like (objects already exist from startup DDL)
@pytest.mark.asyncio
async def test_production_like_converges_without_error_and_preserves_data():
    def body(conn, schema):
        # Insert data into vendor_tracks before upgrade
        _q(conn, "INSERT INTO vendor_tracks (track_id, tenant_id, vendor_id, track_date, points, point_count, status, created_at, updated_at) "
                 "VALUES (gen_random_uuid(), gen_random_uuid(), 'V00002', '2026-02-01', '[]', 0, 'active', now(), now())")
        before_vt = _q(conn, "SELECT count(*) FROM vendor_tracks").scalar()
        before_cons = _unique_constraints_on(conn, schema, "vendor_tracks")

        _run(conn)  # must not error, must not drop data

        after_vt = _q(conn, "SELECT count(*) FROM vendor_tracks").scalar()
        assert after_vt == before_vt, f"vendor_tracks data changed: {before_vt} -> {after_vt}"
        after_cons = _unique_constraints_on(conn, schema, "vendor_tracks")
        assert after_cons == before_cons, f"constraints changed: {before_cons} -> {after_cons}"
    await _scratch(body, prod_state=True)


# ---- 022 adopt-not-recreate with custom constraint name
@pytest.mark.asyncio
async def test_022_adopts_existing_constraint_whatever_its_name():
    def body(conn, schema):
        # vendor_tracks already has a unique constraint from STUBS (named by PostgreSQL)
        cons_before = _unique_constraints_on(conn, schema, "vendor_tracks")
        assert len(cons_before) == 1
        original_name = cons_before.pop()

        _run(conn, ["022_vendor_tracks"])

        cons_after = _unique_constraints_on(conn, schema, "vendor_tracks")
        assert cons_after == {original_name}, f"constraint name changed: {original_name} -> {cons_after}"
        # No NEW constraint was added
        assert len(cons_after) == 1
    await _scratch(body, extra_sql=[
        "CREATE TABLE vendor_tracks (track_id uuid PRIMARY KEY, tenant_id uuid, vendor_id varchar(6), track_date date, "
        "points jsonb DEFAULT '[]', point_count integer DEFAULT 0, total_distance_meters float, start_time timestamptz, "
        "end_time timestamptz, duration_seconds float, status varchar(20) DEFAULT 'active', created_at timestamptz, updated_at timestamptz, "
        "CONSTRAINT my_custom_name UNIQUE (vendor_id, track_date))"
    ])


# ---- 022 creates constraint when absent
@pytest.mark.asyncio
async def test_022_creates_constraint_when_absent():
    def body(conn, schema):
        _run(conn, ["022_vendor_tracks"])
        cons = _unique_constraints_on(conn, schema, "vendor_tracks")
        assert len(cons) == 1, f"expected 1 unique constraint, got {cons}"
    await _scratch(body, extra_sql=[
        "CREATE TABLE vendor_tracks (track_id uuid PRIMARY KEY, tenant_id uuid, vendor_id varchar(6), track_date date, "
        "points jsonb DEFAULT '[]', point_count integer DEFAULT 0, total_distance_meters float, start_time timestamptz, "
        "end_time timestamptz, duration_seconds float, status varchar(20) DEFAULT 'active', created_at timestamptz, updated_at timestamptz)"
    ])


# ---- repeatability
@pytest.mark.asyncio
@pytest.mark.parametrize("prod_state", [False, True], ids=["fresh", "production-like"])
async def test_second_upgrade_changes_nothing(prod_state):
    def body(conn, schema):
        _run(conn)
        tables_before = _tables(conn, schema)
        cols_before = _cols(conn, schema, "evidence")
        _run(conn)
        assert _tables(conn, schema) == tables_before
        assert _cols(conn, schema, "evidence") == cols_before
    await _scratch(body, prod_state=prod_state)


# ---- lock_timeout
@pytest.mark.asyncio
async def test_migrations_set_lock_timeout():
    def body(conn, schema):
        _run(conn)
        assert _q(conn, "SHOW lock_timeout").scalar() == "5s"
    await _scratch(body)
