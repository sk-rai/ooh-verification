"""Persist and seal a Gate 1 inspection submission."""
from alembic import op
import sqlalchemy as sa


revision = "027_inspection_submission"
down_revision = "026_inspection_capture"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("inspection_visit", sa.Column("revision", sa.BigInteger(), nullable=False, server_default="0"))
    op.create_check_constraint("ck_inspection_visit_revision", "inspection_visit", "revision >= 0")
    op.create_table(
        "inspection_visit_submission",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("visit_id", sa.Uuid(), sa.ForeignKey("inspection_visit.id", ondelete="RESTRICT"),
                  nullable=False, unique=True),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("submit_key", sa.String(128), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("manifest", sa.Text(), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_revision", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("accepted_revision > 0", name="ck_inspection_accepted_revision"),
        sa.Column("sealed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("id", "visit_id", name="uq_inspection_submission_visit"),
        sa.ForeignKeyConstraint(["assignment_id", "visit_id", "generation"],
                                ["inspection_assignment.id", "inspection_assignment.visit_id",
                                 "inspection_assignment.generation"], ondelete="RESTRICT"),
    )
    op.create_table(
        "inspection_document_revision",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("document_instance_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.UniqueConstraint("id", "visit_id", "document_instance_id", name="uq_inspection_revision_instance"),
        sa.ForeignKeyConstraint(["document_instance_id", "visit_id"],
                                ["inspection_document_instance.id", "inspection_document_instance.visit_id"],
                                ondelete="RESTRICT"),
    )
    op.create_table(
        "inspection_submission_document",
        sa.Column("submission_id", sa.Uuid(), primary_key=True),
        sa.Column("document_instance_id", sa.Uuid(), primary_key=True),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.CheckConstraint("ordinal > 0", name="ck_inspection_submission_ordinal"),
        sa.UniqueConstraint("submission_id", "ordinal", name="uq_inspection_submission_ordinal"),
        sa.ForeignKeyConstraint(["submission_id", "visit_id"],
                                ["inspection_visit_submission.id", "inspection_visit_submission.visit_id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revision_id", "visit_id", "document_instance_id"],
                                ["inspection_document_revision.id", "inspection_document_revision.visit_id",
                                 "inspection_document_revision.document_instance_id"], ondelete="RESTRICT"),
    )
    for table in ("inspection_document_revision", "inspection_submission_document"):
        op.execute(f"""
            CREATE TRIGGER inspection_submission_identity_guard BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_inspection_capture_identity()
        """)
    op.execute("""
        CREATE FUNCTION guard_inspection_submission_member() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE parent_sealed boolean;
        BEGIN
            SELECT sealed INTO parent_sealed FROM public.inspection_visit_submission
                WHERE id = NEW.submission_id FOR UPDATE;
            IF parent_sealed IS DISTINCT FROM false THEN
                RAISE EXCEPTION 'inspection submission membership is closed' USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER inspection_submission_member_guard BEFORE INSERT ON inspection_submission_document
        FOR EACH ROW EXECUTE FUNCTION guard_inspection_submission_member()
    """)
    op.execute("""
        CREATE FUNCTION guard_inspection_submission() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NOT NEW.sealed THEN RETURN NEW; END IF;
            ELSIF TG_OP = 'UPDATE' AND NOT OLD.sealed AND NEW.sealed
                AND (to_jsonb(NEW) - 'sealed') = (to_jsonb(OLD) - 'sealed') THEN
                IF (SELECT count(*) FROM public.inspection_submission_document
                    WHERE submission_id = OLD.id) = 1 AND EXISTS (
                    SELECT 1 FROM public.inspection_submission_document AS m
                    JOIN public.inspection_document_instance AS d ON d.id = m.document_instance_id
                    WHERE m.submission_id = OLD.id AND m.ordinal = 1
                        AND d.ordinal = 1 AND d.instance_number = 1
                ) THEN
                    RETURN NEW;
                END IF;
            END IF;
            RAISE EXCEPTION 'invalid inspection seal or immutable submission' USING ERRCODE = '55000';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER inspection_submission_guard BEFORE INSERT OR UPDATE OR DELETE ON inspection_visit_submission
        FOR EACH ROW EXECUTE FUNCTION guard_inspection_submission()
    """)
    op.execute("""
        CREATE FUNCTION require_inspection_submission_seal() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM public.inspection_visit_submission AS s
                JOIN public.inspection_visit AS v ON v.id = s.visit_id
                WHERE s.id = NEW.id AND s.sealed AND v.submitted_at = s.submitted_at
                    AND v.assignment_id = s.assignment_id AND v.generation = s.generation
                    AND v.revision = s.accepted_revision
            ) THEN
                RAISE EXCEPTION 'inspection submission must be sealed and accepted' USING ERRCODE = '55000';
            END IF;
            RETURN NULL;
        END;
        $$
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER inspection_submission_must_seal
        AFTER INSERT ON inspection_visit_submission DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION require_inspection_submission_seal()
    """)


def downgrade():
    for table in ("inspection_submission_document", "inspection_document_revision",
                  "inspection_visit_submission"):
        op.drop_table(table)
    for function in ("require_inspection_submission_seal", "guard_inspection_submission",
                     "guard_inspection_submission_member"):
        op.execute(f"DROP FUNCTION {function}()")
    op.drop_constraint("ck_inspection_visit_revision", "inspection_visit", type_="check")
    op.drop_column("inspection_visit", "revision")
