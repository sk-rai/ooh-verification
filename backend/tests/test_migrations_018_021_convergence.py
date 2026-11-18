"""
Migrations 018-021 must converge from ANY starting state (M1 of the migration-drift repair).

Why: production sits at revision 017 because 019 fails with DuplicateColumnError (the same columns are created by the
startup DDL in app/main.py), and Alembic runs the whole upgrade in ONE transaction, so every deploy rolls back 018-021.
Reproduced on PostgreSQL 18 with the unmodified migrations:
  * 019: ADD COLUMN on columns that already exist                      -> DuplicateColumnError
  * 020: drop_constraint wrapped in try/except; PostgreSQL has already aborted the transaction, so the NEXT statement
         (CREATE INDEX) fails with InFailedSQLTransactionError         -> whole upgrade fails
  * 021: CREATE TABLE cases / evidence / gps_tracks that already exist -> DuplicateTableError
  * 018 (fresh install): task_queue.status created as TEXT while the model and startup DDL use the native enum
         taskstatus, so dequeue fails with "operator does not exist: text = taskstatus"
  * 021 would also add six indexes production never received.

How these tests run: each test works inside ONE transaction on the disposable test database, in a throw-away schema, and
always rolls back (the test role has no CREATEDB; nothing persists). The real migration modules are executed through
Alembic's Operations API, so the exact production code paths run. The end-to-end `alembic upgrade head` on
PostgreSQL 18 is covered separately by the reproduction harness.
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
MIGRATIONS = ["018_task_queue", "019_motion_sensors", "020_multi_location", "021_evidence_table"]

SIX_INDEXES = {
    "ix_cases_client_id", "ix_cases_tenant_id", "ix_evidence_evidence_id",
    "ix_evidence_category", "ix_evidence_tenant_type", "ix_evidence_campaign_vendor",
}


# --------------------------------------------------------------------------- helpers
def _load(name):
    spec = importlib.util.spec_from_file_location(f"mig_{name}", VERSIONS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(conn, names=MIGRATIONS):
    """Execute upgrade() of each migration, in order, on this (sync) connection through Alembic's Operations."""
    ctx = MigrationContext.configure(conn)
    with Operations.context(ctx):
        for n in names:
            _load(n).upgrade()


def _q(conn, sql, **p):
    return conn.execute(text(sql), p)


# Tables the migrations depend on (created by migrations before 018 in real life).
STUBS = [
    "CREATE TABLE clients (client_id uuid PRIMARY KEY)",
    "CREATE TABLE campaigns (campaign_id uuid PRIMARY KEY)",
    "CREATE TABLE vendors (vendor_id varchar(6) PRIMARY KEY)",
    "CREATE TABLE sensor_data (sensor_id uuid PRIMARY KEY)",
    "CREATE TABLE location_profiles (profile_id uuid PRIMARY KEY, campaign_id uuid NOT NULL UNIQUE)",
    "CREATE INDEX idx_location_profiles_campaign ON location_profiles (campaign_id)",
]

# What production has today: created by app/main.py startup DDL (task_queue from the model: enum status, no defaults).
PROD_STATE = [
    "DO $$ BEGIN CREATE TYPE taskstatus AS ENUM ('pending','running','completed','failed','dead'); "
    "EXCEPTION WHEN duplicate_object THEN NULL; END $$",
    "CREATE TABLE task_queue (id uuid PRIMARY KEY, task_type varchar(100) NOT NULL, payload jsonb NOT NULL, "
    "status taskstatus NOT NULL, priority integer NOT NULL, created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL, "
    "scheduled_at timestamptz NOT NULL, started_at timestamptz, completed_at timestamptz, retry_count integer NOT NULL, "
    "max_retries integer NOT NULL, last_error text, tenant_id uuid)",
    "CREATE INDEX ix_task_queue_task_type ON task_queue (task_type)",
    "CREATE INDEX ix_task_queue_status ON task_queue (status)",
    "CREATE INDEX ix_task_queue_tenant_id ON task_queue (tenant_id)",
    "CREATE INDEX ix_task_queue_poll ON task_queue (status, scheduled_at, priority)",
    "ALTER TABLE sensor_data ADD COLUMN accelerometer_data jsonb, ADD COLUMN gyroscope_data jsonb, "
    "ADD COLUMN orientation_data jsonb",
    "CREATE TABLE cases (case_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, "
    "client_id uuid NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE, title varchar(255) NOT NULL, description text, "
    "category varchar(50), status varchar(20) NOT NULL DEFAULT 'open', created_at timestamptz NOT NULL DEFAULT now(), "
    "updated_at timestamptz NOT NULL DEFAULT now())",
    "CREATE TABLE evidence (evidence_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, "
    "campaign_id uuid REFERENCES campaigns(campaign_id) ON DELETE SET NULL, "
    "vendor_id varchar(6) NOT NULL REFERENCES vendors(vendor_id) ON DELETE CASCADE, "
    "case_id uuid REFERENCES cases(case_id) ON DELETE SET NULL, evidence_type varchar(20) NOT NULL, category varchar(50), "
    "file_key varchar(500), file_url varchar(500), thumbnail_key varchar(500), thumbnail_url varchar(500), "
    "file_size_bytes bigint, mime_type varchar(50), duration_seconds float, text_content text, capture_timestamp timestamptz, "
    "latitude float, longitude float, accuracy float, verification_status varchar(20) NOT NULL DEFAULT 'pending', "
    "verification_confidence float, verification_flags jsonb DEFAULT '[]', device_signature text, file_hash varchar(128), "
    "sensor_data jsonb, tags jsonb DEFAULT '[]', metadata jsonb DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), "
    "updated_at timestamptz NOT NULL DEFAULT now(), signing_key_id uuid, signing_key_fingerprint varchar(64), "
    "signature_outcome varchar(30))",
    "CREATE TABLE gps_tracks (track_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "
    "evidence_id uuid NOT NULL REFERENCES evidence(evidence_id) ON DELETE CASCADE UNIQUE, points jsonb NOT NULL, "
    "duration_seconds float, total_distance_meters float, created_at timestamptz NOT NULL DEFAULT now())",
    "CREATE INDEX ix_evidence_tenant_id ON evidence (tenant_id)",
    "CREATE INDEX ix_evidence_campaign_id ON evidence (campaign_id)",
    "CREATE INDEX ix_evidence_vendor_id ON evidence (vendor_id)",
    "CREATE INDEX ix_evidence_type ON evidence (evidence_type)",
    "CREATE INDEX ix_evidence_status ON evidence (verification_status)",
    "CREATE INDEX ix_evidence_created ON evidence (created_at)",
    "CREATE INDEX ix_gps_tracks_evidence_id ON gps_tracks (evidence_id)",
    "ALTER TABLE location_profiles ADD COLUMN asset_id varchar(100), ADD COLUMN asset_type varchar(50), "
    "ADD COLUMN location_description text",
    "ALTER TABLE location_profiles DROP CONSTRAINT location_profiles_campaign_id_key",
    "CREATE INDEX ix_location_profiles_campaign_id ON location_profiles (campaign_id)",
]


def _snapshot(conn, schema):
    cols = _q(conn, "SELECT table_name, column_name, udt_name, is_nullable, coalesce(column_default,'-') "
                    "FROM information_schema.columns WHERE table_schema=:s ORDER BY 1,2", s=schema).fetchall()
    idx = _q(conn, "SELECT tablename, indexname, replace(indexdef, :s || '.', '') FROM pg_indexes "
                   "WHERE schemaname=:s ORDER BY 1,2", s=schema).fetchall()
    con = _q(conn, "SELECT cl.relname, co.conname, CAST(co.contype AS text), pg_get_constraintdef(co.oid) "
                   "FROM pg_constraint co JOIN pg_class cl ON cl.oid=co.conrelid JOIN pg_namespace n ON n.oid=cl.relnamespace "
                   "WHERE n.nspname=:s ORDER BY 1,2", s=schema).fetchall()
    return [tuple(r) for r in cols], [tuple(r) for r in idx], [tuple(r) for r in con]


def _indexes(conn, schema):
    return {r[0] for r in _q(conn, "SELECT indexname FROM pg_indexes WHERE schemaname=:s", s=schema)}


def _col(conn, schema, table, col):
    r = _q(conn, "SELECT udt_name, column_default FROM information_schema.columns WHERE table_schema=:s "
                 "AND table_name=:t AND column_name=:c", s=schema, t=table, c=col).fetchone()
    return tuple(r) if r else None


def _unique_constraints_on(conn, schema, table):
    return {r[0] for r in _q(conn, "SELECT co.conname FROM pg_constraint co JOIN pg_class cl ON cl.oid=co.conrelid "
                                   "JOIN pg_namespace n ON n.oid=cl.relnamespace WHERE n.nspname=:s AND cl.relname=:t "
                                   "AND co.contype='u'", s=schema, t=table)}


async def _scratch(body, *, prod_state=False, extra_sql=()):
    """Run body(sync_conn, schema) in a rolled-back transaction inside a throw-away schema."""
    schema = "m1_" + uuid.uuid4().hex[:10]
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.connect() as aconn:
            trans = await aconn.begin()
            try:
                def work(conn):
                    _q(conn, f'CREATE SCHEMA "{schema}"')
                    _q(conn, f'SET LOCAL search_path TO "{schema}", public')
                    for stmt in STUBS + (PROD_STATE if prod_state else []) + list(extra_sql):
                        _q(conn, stmt)
                    return body(conn, schema)
                return await aconn.run_sync(work)
            finally:
                await trans.rollback()
    finally:
        await engine.dispose()


# --------------------------------------------------------------------------- the migration graph
def test_graph_is_a_single_linear_chain_018_to_021():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    # M2 extends the chain; 021 is no longer the head but must still be in it
    head = script.get_heads()[0]
    assert head in ("021_evidence", "024_schema_additions"), f"unexpected head {head}"
    expected = [("024_schema_additions", "023_api_keys_device_keys"),
                ("023_api_keys_device_keys", "022_vendor_tracks"),
                ("022_vendor_tracks", "021_evidence"),
                ("021_evidence", "020_multi_location"),
                ("020_multi_location", "019_motion_sensors"),
                ("019_motion_sensors", "018_task_queue"),
                ("018_task_queue", "017_visitor_analytics")]
    for rev, down in expected:
        assert script.get_revision(rev).down_revision == down


# --------------------------------------------------------------------------- fresh install
@pytest.mark.asyncio
async def test_fresh_install_converges_with_the_enum_status_the_app_expects():
    def body(conn, schema):
        _run(conn)
        status = _col(conn, schema, "task_queue", "status")
        assert status[0] == "taskstatus", f"task_queue.status is {status[0]} but the model/startup DDL use the enum"
        assert "pending" in (status[1] or "")                                  # default kept
        # the app's own dequeue shape: compare the column to the enum and move a task through the states
        _q(conn, "INSERT INTO task_queue (task_type, payload) VALUES ('t', '{}')")
        assert _q(conn, "SELECT count(*) FROM task_queue WHERE status = CAST('pending' AS taskstatus)").scalar() == 1
        _q(conn, "UPDATE task_queue SET status = CAST('running' AS taskstatus) "
                 "WHERE status = CAST('pending' AS taskstatus)")
        assert SIX_INDEXES <= _indexes(conn, schema)
        assert {"ix_task_queue_poll", "ix_evidence_tenant_id", "ix_evidence_created", "ix_gps_tracks_evidence_id",
                "ix_location_profiles_campaign_id"} <= _indexes(conn, schema)
        assert _unique_constraints_on(conn, schema, "location_profiles") == set()
        for c in ("accelerometer_data", "gyroscope_data", "orientation_data"):
            assert _col(conn, schema, "sensor_data", c) is not None
        for c in ("asset_id", "asset_type", "location_description"):
            assert _col(conn, schema, "location_profiles", c) is not None
        for t, pk in (("cases", "case_id"), ("evidence", "evidence_id"), ("gps_tracks", "track_id")):
            assert _col(conn, schema, t, pk) is not None
    await _scratch(body)


# --------------------------------------------------------------------------- production-like state
@pytest.mark.asyncio
async def test_production_like_state_upgrades_without_error_and_only_adds_the_six_indexes():
    def body(conn, schema):
        _q(conn, "INSERT INTO clients VALUES (gen_random_uuid())")
        _q(conn, "INSERT INTO vendors VALUES ('V00001')")
        _q(conn, "INSERT INTO evidence (tenant_id, vendor_id, evidence_type) SELECT gen_random_uuid(), 'V00001', 'photo' "
                 "FROM generate_series(1,5)")
        _q(conn, "INSERT INTO task_queue (id, task_type, payload, status, priority, created_at, updated_at, scheduled_at, "
                 "retry_count, max_retries) VALUES (gen_random_uuid(), 't', '{}', 'pending', 0, now(), now(), now(), 0, 3)")
        ev_sql = "SELECT md5(string_agg(e::text, '|' ORDER BY e::text)) FROM evidence e"
        tq_sql = "SELECT md5(string_agg(t::text, '|' ORDER BY t::text)) FROM task_queue t"
        before = _snapshot(conn, schema)
        rows_before, tq_before = _q(conn, ev_sql).scalar(), _q(conn, tq_sql).scalar()

        _run(conn)                                                            # RED today: DuplicateColumnError (019)

        cols_a, idx_a, con_a = before
        cols_b, idx_b, con_b = _snapshot(conn, schema)
        assert cols_b == cols_a, "columns changed on a production-like database"
        assert con_b == con_a, "constraints changed on a production-like database"
        added = {i[1] for i in idx_b} - {i[1] for i in idx_a}
        assert added == SIX_INDEXES, f"expected exactly the six missing indexes, got {sorted(added)}"
        assert set(idx_a) <= set(idx_b), "an existing index was altered or removed"
        assert _q(conn, ev_sql).scalar() == rows_before
        assert _q(conn, tq_sql).scalar() == tq_before
        assert _col(conn, schema, "task_queue", "status")[0] == "taskstatus"      # not converted, not touched
    await _scratch(body, prod_state=True)


# --------------------------------------------------------------------------- repeatability
@pytest.mark.asyncio
@pytest.mark.parametrize("prod_state", [False, True], ids=["fresh", "production-like"])
async def test_a_second_upgrade_changes_nothing(prod_state):
    def body(conn, schema):
        _run(conn)
        first = _snapshot(conn, schema)
        _run(conn)
        assert _snapshot(conn, schema) == first
    await _scratch(body, prod_state=prod_state)


# --------------------------------------------------------------------------- 019
@pytest.mark.asyncio
async def test_019_tolerates_partially_present_columns():
    def body(conn, schema):
        _run(conn, ["019_motion_sensors"])
        for c in ("accelerometer_data", "gyroscope_data", "orientation_data"):
            assert _col(conn, schema, "sensor_data", c)[0] == "jsonb"
    await _scratch(body, extra_sql=["ALTER TABLE sensor_data ADD COLUMN accelerometer_data jsonb"])


# --------------------------------------------------------------------------- 020
@pytest.mark.asyncio
async def test_020_does_not_abort_the_transaction_when_the_constraint_is_already_gone():
    def body(conn, schema):
        _run(conn, ["020_multi_location"])                                    # RED today: InFailedSQLTransactionError
        assert "ix_location_profiles_campaign_id" in _indexes(conn, schema)
    await _scratch(body, extra_sql=["ALTER TABLE location_profiles DROP CONSTRAINT location_profiles_campaign_id_key"])


@pytest.mark.asyncio
async def test_020_drops_the_single_column_unique_constraint_whatever_its_name_and_keeps_others():
    def body(conn, schema):
        before = _unique_constraints_on(conn, schema, "location_profiles")
        assert {"uq_custom_name", "uq_campaign_and_profile"} <= before
        _run(conn, ["020_multi_location"])
        after = _unique_constraints_on(conn, schema, "location_profiles")
        assert "uq_custom_name" not in after
        assert "uq_campaign_and_profile" in after, "a composite unique constraint must not be dropped"
        # multi-location now works
        _q(conn, "INSERT INTO location_profiles (profile_id, campaign_id) SELECT gen_random_uuid(), "
                 "'00000000-0000-0000-0000-000000000001' FROM generate_series(1,2)")
    await _scratch(body, extra_sql=[
        "ALTER TABLE location_profiles DROP CONSTRAINT location_profiles_campaign_id_key",
        "ALTER TABLE location_profiles ADD CONSTRAINT uq_custom_name UNIQUE (campaign_id)",
        "ALTER TABLE location_profiles ADD CONSTRAINT uq_campaign_and_profile UNIQUE (campaign_id, profile_id)"])


@pytest.mark.asyncio
async def test_020_drops_the_standard_named_constraint_when_present():
    def body(conn, schema):
        assert "location_profiles_campaign_id_key" in _unique_constraints_on(conn, schema, "location_profiles")
        _run(conn, ["020_multi_location"])
        assert _unique_constraints_on(conn, schema, "location_profiles") == set()
    await _scratch(body)


# --------------------------------------------------------------------------- 021
@pytest.mark.asyncio
async def test_021_tolerates_existing_tables_and_indexes():
    def body(conn, schema):
        _run(conn, ["021_evidence_table"])
        assert SIX_INDEXES <= _indexes(conn, schema)
        for c in ("asset_id", "asset_type", "location_description"):
            assert _col(conn, schema, "location_profiles", c) is not None
    await _scratch(body, prod_state=True)


# --------------------------------------------------------------------------- safety
@pytest.mark.asyncio
async def test_the_migrations_bound_how_long_they_may_wait_for_locks():
    def body(conn, schema):
        _run(conn)
        assert _q(conn, "SHOW lock_timeout").scalar() == "5s"
    await _scratch(body)
