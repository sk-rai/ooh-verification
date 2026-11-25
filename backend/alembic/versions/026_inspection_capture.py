"""Pin inspection documents and reserve exact photo targets."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "026_inspection_capture"
down_revision = "025_gate1_visit_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("inspection_visit", sa.Column("package_sealed_at", sa.DateTime(timezone=True)))
    op.create_unique_constraint("uq_inspection_visit_owner_scope", "inspection_visit",
                                ["id", "tenant_id", "owner_client_id"])
    op.create_unique_constraint("uq_inspection_assignment_scope", "inspection_assignment",
                                ["id", "visit_id", "generation"])
    op.create_table(
        "inspection_form_version",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("owner_client_id", sa.Uuid(), nullable=False),
        sa.Column("definition", JSONB(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("jsonb_typeof(definition) = 'object'", name="ck_inspection_form_object"),
        sa.UniqueConstraint("id", "tenant_id", "owner_client_id", name="uq_form_version_owner"),
        sa.ForeignKeyConstraint(["owner_client_id", "tenant_id"],
                                ["clients.client_id", "clients.tenant_id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "inspection_workflow_version",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("owner_client_id", sa.Uuid(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("id", "tenant_id", "owner_client_id", name="uq_inspection_workflow_owner"),
        sa.ForeignKeyConstraint(["owner_client_id", "tenant_id"],
                                ["clients.client_id", "clients.tenant_id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "inspection_document_requirement",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("owner_client_id", sa.Uuid(), nullable=False),
        sa.Column("form_version_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("min_instances", sa.Integer(), nullable=False),
        sa.Column("max_instances", sa.Integer(), nullable=False),
        sa.Column("activation_condition", JSONB(none_as_null=True)),
        sa.CheckConstraint("activation_condition IS NULL OR jsonb_typeof(activation_condition) = 'object'",
                           name="ck_inspection_requirement_condition"),
        sa.CheckConstraint("position > 0 AND min_instances >= 0 AND max_instances >= min_instances",
                           name="ck_inspection_requirement_cardinality"),
        sa.UniqueConstraint("workflow_version_id", "position", name="uq_inspection_requirement_position"),
        sa.UniqueConstraint("id", "workflow_version_id", "form_version_id",
                            name="uq_inspection_requirement_form"),
        sa.ForeignKeyConstraint(["workflow_version_id", "tenant_id", "owner_client_id"],
                                ["inspection_workflow_version.id", "inspection_workflow_version.tenant_id",
                                 "inspection_workflow_version.owner_client_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["form_version_id", "tenant_id", "owner_client_id"],
                                ["inspection_form_version.id", "inspection_form_version.tenant_id",
                                 "inspection_form_version.owner_client_id"], ondelete="RESTRICT"),
    )
    op.add_column("inspection_visit", sa.Column("workflow_version_id", sa.Uuid()))
    op.create_foreign_key("fk_inspection_visit_workflow", "inspection_visit", "inspection_workflow_version",
                          ["workflow_version_id", "tenant_id", "owner_client_id"],
                          ["id", "tenant_id", "owner_client_id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_inspection_visit_workflow", "inspection_visit", ["id", "workflow_version_id"])
    op.create_table(
        "inspection_document_instance",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("owner_client_id", sa.Uuid(), nullable=False),
        sa.Column("form_version_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("instance_number", sa.Integer(), nullable=False),
        sa.UniqueConstraint("visit_id", "requirement_id", "instance_number",
                            name="uq_inspection_requirement_instance"),
        sa.ForeignKeyConstraint(["visit_id", "workflow_version_id"],
                                ["inspection_visit.id", "inspection_visit.workflow_version_id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requirement_id", "workflow_version_id", "form_version_id"],
                                ["inspection_document_requirement.id",
                                 "inspection_document_requirement.workflow_version_id",
                                 "inspection_document_requirement.form_version_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("ordinal > 0 AND instance_number > 0", name="ck_inspection_document_ordinal"),
        sa.UniqueConstraint("id", "visit_id", name="uq_inspection_document_visit"),
        sa.UniqueConstraint("visit_id", "ordinal", name="uq_inspection_document_ordinal"),
        sa.ForeignKeyConstraint(["visit_id", "tenant_id", "owner_client_id"],
                                ["inspection_visit.id", "inspection_visit.tenant_id",
                                 "inspection_visit.owner_client_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["form_version_id", "tenant_id", "owner_client_id"],
                                ["inspection_form_version.id", "inspection_form_version.tenant_id",
                                 "inspection_form_version.owner_client_id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "inspection_capture_target",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_instance_id", sa.Uuid(), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("field_id", sa.String(100), nullable=False),
        sa.Column("slot_id", sa.String(100), nullable=False),
        sa.Column("repeat_item_id", sa.Uuid()),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("id", "visit_id", name="uq_inspection_capture_target_visit"),
        sa.ForeignKeyConstraint(["document_instance_id", "visit_id"],
                                ["inspection_document_instance.id", "inspection_document_instance.visit_id"],
                                ondelete="RESTRICT"),
    )
    op.execute("""
        CREATE UNIQUE INDEX uq_inspection_capture_repeat_target
        ON inspection_capture_target(document_instance_id, field_id, slot_id, repeat_item_id)
        WHERE repeat_item_id IS NOT NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_inspection_capture_single_target
        ON inspection_capture_target(document_instance_id, field_id, slot_id)
        WHERE repeat_item_id IS NULL
    """)
    op.create_table(
        "inspection_upload_reservation",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("client_capture_id", sa.Uuid(), nullable=False),
        sa.Column("upload_key", sa.String(128), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("byte_length", sa.Integer(), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("byte_length BETWEEN 1 AND 10485760", name="ck_inspection_capture_size"),
        sa.CheckConstraint("digest ~ '^[0-9a-f]{64}$'", name="ck_inspection_capture_digest"),
        sa.UniqueConstraint("assignment_id", "upload_key", name="uq_inspection_reservation_key"),
        sa.UniqueConstraint("assignment_id", "client_capture_id", name="uq_inspection_reservation_capture"),
        sa.ForeignKeyConstraint(["assignment_id", "visit_id", "generation"],
                                ["inspection_assignment.id", "inspection_assignment.visit_id",
                                 "inspection_assignment.generation"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_id", "visit_id"],
                                ["inspection_capture_target.id", "inspection_capture_target.visit_id"],
                                ondelete="RESTRICT"),
    )
    op.create_table(
        "inspection_capture_receipt",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("reservation_id", sa.Uuid(),
                  sa.ForeignKey("inspection_upload_reservation.id", ondelete="RESTRICT"), unique=True, nullable=False),
        sa.Column("evidence_id", sa.Uuid(),
                  sa.ForeignKey("evidence.evidence_id", ondelete="RESTRICT"), unique=True, nullable=False),
        sa.Column("key_id", sa.Uuid(), sa.ForeignKey("device_keys.key_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verification_method", sa.String(40), nullable=False),
    )
    op.execute("""
        CREATE FUNCTION guard_inspection_capture_identity() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'inspection form, target and reservation pins are immutable' USING ERRCODE = '55000';
        END;
        $$
    """)
    op.execute("""
        CREATE FUNCTION guard_inspection_package_membership() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE sealed_at timestamptz;
        BEGIN
            SELECT package_sealed_at INTO sealed_at
            FROM public.inspection_visit WHERE id = NEW.visit_id FOR UPDATE;
            IF sealed_at IS NOT NULL THEN
                RAISE EXCEPTION 'inspection package is sealed' USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    for table in ("inspection_document_instance", "inspection_capture_target"):
        op.execute(f"""
            CREATE TRIGGER inspection_package_membership_guard BEFORE INSERT ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_inspection_package_membership()
        """)
    op.execute("""
        CREATE FUNCTION guard_inspection_package_seal() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.package_sealed_at IS NOT NULL THEN
                    RAISE EXCEPTION 'inspection package must be sealed after provisioning' USING ERRCODE = '55000';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.package_sealed_at IS NOT NULL AND NEW.package_sealed_at IS DISTINCT FROM OLD.package_sealed_at THEN
                RAISE EXCEPTION 'inspection package seal is immutable' USING ERRCODE = '55000';
            END IF;
            IF OLD.package_sealed_at IS NULL AND NEW.package_sealed_at IS NOT NULL THEN
                IF NOT EXISTS (SELECT 1 FROM public.inspection_document_instance WHERE visit_id = NEW.id) THEN
                    RAISE EXCEPTION 'inspection package requires a document' USING ERRCODE = '55000';
                END IF;
                NEW.package_sealed_at = pg_catalog.clock_timestamp();
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER inspection_package_seal_guard
        BEFORE INSERT OR UPDATE OF package_sealed_at ON inspection_visit
        FOR EACH ROW EXECUTE FUNCTION guard_inspection_package_seal()
    """)
    op.execute("""
        CREATE FUNCTION guard_inspection_workflow_publication() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.published_at IS NULL THEN RETURN NEW; END IF;
            ELSIF TG_OP = 'DELETE' THEN
                IF OLD.published_at IS NULL THEN RETURN OLD; END IF;
            ELSE
                IF OLD.published_at IS NULL AND
                   (NEW.id, NEW.tenant_id, NEW.owner_client_id) =
                   (OLD.id, OLD.tenant_id, OLD.owner_client_id) AND
                   NEW.published_at IS NOT NULL AND EXISTS (
                       SELECT 1 FROM public.inspection_document_requirement WHERE workflow_version_id = OLD.id
                   ) THEN
                    NEW.published_at = pg_catalog.clock_timestamp();
                    RETURN NEW;
                END IF;
            END IF;
            RAISE EXCEPTION 'invalid inspection workflow publication' USING ERRCODE = '55000';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER inspection_workflow_publication_guard
        BEFORE INSERT OR UPDATE OR DELETE ON inspection_workflow_version
        FOR EACH ROW EXECUTE FUNCTION guard_inspection_workflow_publication()
    """)
    op.execute("""
        CREATE FUNCTION guard_inspection_requirement_insert() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE publication timestamptz;
        BEGIN
            SELECT published_at INTO publication FROM public.inspection_workflow_version
            WHERE id = NEW.workflow_version_id FOR UPDATE;
            IF publication IS NOT NULL THEN
                RAISE EXCEPTION 'inspection workflow is published' USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER inspection_requirement_insert_guard
        BEFORE INSERT ON inspection_document_requirement
        FOR EACH ROW EXECUTE FUNCTION guard_inspection_requirement_insert()
    """)
    op.execute("""
        CREATE FUNCTION guard_inspection_workflow_pin() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' AND OLD.workflow_version_id IS NOT NULL
                AND NEW.workflow_version_id IS DISTINCT FROM OLD.workflow_version_id THEN
                RAISE EXCEPTION 'inspection workflow pin is immutable' USING ERRCODE = '55000';
            END IF;
            IF NEW.workflow_version_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM public.inspection_workflow_version
                WHERE id = NEW.workflow_version_id AND published_at IS NOT NULL
            ) THEN
                RAISE EXCEPTION 'inspection workflow is unpublished' USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER inspection_workflow_pin_guard
        BEFORE INSERT OR UPDATE OF workflow_version_id ON inspection_visit
        FOR EACH ROW EXECUTE FUNCTION guard_inspection_workflow_pin()
    """)
    for table in ("inspection_form_version", "inspection_document_requirement", "inspection_document_instance",
                  "inspection_capture_target", "inspection_upload_reservation", "inspection_capture_receipt"):
        op.execute(f"""
            CREATE TRIGGER inspection_capture_identity_guard BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_inspection_capture_identity()
        """)


def downgrade():
    op.execute("DROP TRIGGER inspection_package_seal_guard ON inspection_visit")
    op.execute("DROP TRIGGER inspection_workflow_pin_guard ON inspection_visit")
    for table in ("inspection_capture_receipt", "inspection_upload_reservation", "inspection_capture_target",
                  "inspection_document_instance", "inspection_document_requirement", "inspection_form_version"):
        op.drop_table(table)
    op.execute("DROP FUNCTION guard_inspection_capture_identity()")
    op.execute("DROP FUNCTION guard_inspection_package_seal()")
    op.execute("DROP FUNCTION guard_inspection_package_membership()")
    op.drop_constraint("uq_inspection_visit_workflow", "inspection_visit", type_="unique")
    op.drop_constraint("fk_inspection_visit_workflow", "inspection_visit", type_="foreignkey")
    op.drop_column("inspection_visit", "workflow_version_id")
    op.drop_table("inspection_workflow_version")
    op.execute("DROP FUNCTION guard_inspection_workflow_pin()")
    op.execute("DROP FUNCTION guard_inspection_workflow_publication()")
    op.execute("DROP FUNCTION guard_inspection_requirement_insert()")
    op.drop_column("inspection_visit", "package_sealed_at")
    op.drop_constraint("uq_inspection_assignment_scope", "inspection_assignment", type_="unique")
    op.drop_constraint("uq_inspection_visit_owner_scope", "inspection_visit", type_="unique")
