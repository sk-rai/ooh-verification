"""Gate 1 inspection visit ownership and key revocation.

Revision ID: 025_gate1_visit_auth
Revises: 024_schema_additions
"""
from alembic import op
import sqlalchemy as sa


revision = "025_gate1_visit_auth"
down_revision = "024_schema_additions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_client_tenant", "clients", ["client_id", "tenant_id"])
    op.create_unique_constraint("uq_vendor_tenant", "vendors", ["vendor_id", "tenant_id"])
    op.add_column("vendors", sa.Column("inspection_enrollment_nonce", sa.Uuid()))
    op.add_column("device_keys", sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.add_column("device_keys", sa.Column("inspection_enrollment_id", sa.Uuid()))
    op.create_unique_constraint("uq_device_key_inspection_enrollment", "device_keys", ["inspection_enrollment_id"])
    op.create_table(
        "inspection_visit",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("owner_client_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_id", sa.String(6), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("generation", sa.BigInteger(), nullable=False, server_default="1"),
        sa.CheckConstraint("generation > 0", name="ck_inspection_visit_generation"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("id", "tenant_id", name="uq_inspection_visit_tenant"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant_config.tenant_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["owner_client_id", "tenant_id"], ["clients.client_id", "clients.tenant_id"],
            name="fk_inspection_visit_client_tenant", onupdate="RESTRICT", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id", "tenant_id"], ["vendors.vendor_id", "vendors.tenant_id"],
            name="fk_inspection_visit_vendor_tenant", onupdate="RESTRICT", ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "inspection_assignment",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_id", sa.String(6), nullable=False),
        sa.UniqueConstraint("visit_id", "generation", name="uq_inspection_assignment_generation"),
        sa.ForeignKeyConstraint(
            ["visit_id", "tenant_id"], ["inspection_visit.id", "inspection_visit.tenant_id"],
            name="fk_inspection_assignment_visit_tenant", onupdate="RESTRICT", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id", "tenant_id"], ["vendors.vendor_id", "vendors.tenant_id"],
            onupdate="RESTRICT", ondelete="RESTRICT",
        ),
    )
    op.execute("""
        CREATE FUNCTION public.record_inspection_assignment() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        BEGIN
            IF TG_OP = 'INSERT' OR NEW.generation <> OLD.generation THEN
                INSERT INTO public.inspection_assignment (id, visit_id, generation, tenant_id, vendor_id)
                VALUES (NEW.assignment_id, NEW.id, NEW.generation, NEW.tenant_id, NEW.vendor_id);
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("REVOKE EXECUTE ON FUNCTION public.record_inspection_assignment() FROM PUBLIC")
    op.execute("""
        CREATE TRIGGER inspection_assignment_record
        AFTER INSERT OR UPDATE ON inspection_visit
        FOR EACH ROW EXECUTE FUNCTION public.record_inspection_assignment()
    """)
    op.execute("""
        CREATE FUNCTION guard_inspection_assignment() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'inspection assignment history is immutable' USING ERRCODE = '55000';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER inspection_assignment_immutable
        BEFORE UPDATE OR DELETE ON inspection_assignment
        FOR EACH ROW EXECUTE FUNCTION guard_inspection_assignment()
    """)

    op.create_index("ix_inspection_visit_owner", "inspection_visit", ["owner_client_id", "tenant_id"])
    op.create_index("ix_inspection_visit_vendor", "inspection_visit", ["vendor_id", "tenant_id"])
    op.execute("""
        CREATE FUNCTION guard_inspection_visit_identity() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.generation <> 1 OR NEW.submitted_at IS NOT NULL THEN
                    RAISE EXCEPTION 'initial assignment generation must be one' USING ERRCODE = '55000';
                END IF;
                RETURN NEW;
            END IF;
            IF (NEW.id, NEW.tenant_id, NEW.owner_client_id, NEW.expires_at)
                IS DISTINCT FROM (OLD.id, OLD.tenant_id, OLD.owner_client_id, OLD.expires_at)
                OR ((OLD.revoked_at IS NOT NULL OR OLD.submitted_at IS NOT NULL)
                    AND NEW IS DISTINCT FROM OLD) THEN
                RAISE EXCEPTION 'inspection visit identity or revoked visit cannot change'
                    USING ERRCODE = '55000';
            END IF;
            IF NEW.submitted_at IS NOT NULL AND (NEW.revoked_at IS NOT NULL
                OR NEW.generation <> OLD.generation OR clock_timestamp() > OLD.expires_at) THEN
                RAISE EXCEPTION 'invalid submission transition' USING ERRCODE = '55000';
            END IF;
            IF NEW.generation <> OLD.generation THEN
                IF NEW.generation <> OLD.generation + 1 OR NEW.assignment_id = OLD.assignment_id
                    OR NEW.revoked_at IS NOT NULL OR clock_timestamp() > OLD.expires_at THEN
                    RAISE EXCEPTION 'invalid reassignment' USING ERRCODE = '55000';
                END IF;
            ELSIF (NEW.assignment_id, NEW.vendor_id) IS DISTINCT FROM (OLD.assignment_id, OLD.vendor_id) THEN
                RAISE EXCEPTION 'reassignment requires a new generation' USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER inspection_visit_identity_guard
        BEFORE INSERT OR UPDATE ON inspection_visit
        FOR EACH ROW EXECUTE FUNCTION guard_inspection_visit_identity()
    """)


def downgrade():
    op.drop_table("inspection_assignment")
    op.drop_table("inspection_visit")
    op.execute("DROP FUNCTION public.record_inspection_assignment()")
    op.execute("DROP FUNCTION guard_inspection_assignment()")
    op.execute("DROP FUNCTION guard_inspection_visit_identity()")
    op.drop_constraint("uq_device_key_inspection_enrollment", "device_keys", type_="unique")
    op.drop_column("device_keys", "inspection_enrollment_id")
    op.drop_column("device_keys", "revoked_at")
    op.drop_column("vendors", "inspection_enrollment_nonce")
    op.drop_constraint("uq_vendor_tenant", "vendors", type_="unique")
    op.drop_constraint("uq_client_tenant", "clients", type_="unique")
