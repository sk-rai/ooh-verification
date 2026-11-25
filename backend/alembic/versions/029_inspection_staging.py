"""Stage complete originals and pin the backend for each finalized receipt."""
from alembic import op
import sqlalchemy as sa

revision = "029_inspection_staging"
down_revision = "028_inspection_storage_fence"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inspection_original_staging",
        sa.Column("reservation_id", sa.Uuid(), sa.ForeignKey(
            "inspection_upload_reservation.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("backend_id", sa.String(64), nullable=False),
        sa.Column("content", sa.LargeBinary()),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("octet_length(content) BETWEEN 1 AND 10485760",
                           name="ck_inspection_staging_length"),
    )
    op.add_column("inspection_capture_receipt", sa.Column(
        "storage_backend_id", sa.String(64), nullable=False, server_default="legacy"))
    op.add_column("inspection_capture_receipt", sa.Column("storage_reference", sa.String(500)))
    op.create_check_constraint(
        "ck_inspection_storage_reference", "inspection_capture_receipt",
        "storage_backend_id = 'legacy' OR storage_reference IS NOT NULL",
    )
    op.execute("""
        CREATE FUNCTION guard_inspection_staging_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.reservation_id IS DISTINCT FROM OLD.reservation_id
                OR NEW.backend_id IS DISTINCT FROM OLD.backend_id
                OR NEW.received_at IS DISTINCT FROM OLD.received_at OR NEW.content IS NOT NULL THEN
                RAISE EXCEPTION 'inspection staging receipt is immutable' USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER inspection_staging_receipt_guard BEFORE UPDATE ON inspection_original_staging
        FOR EACH ROW EXECUTE FUNCTION guard_inspection_staging_receipt();
    """)


def downgrade():
    op.drop_constraint("ck_inspection_storage_reference", "inspection_capture_receipt", type_="check")
    op.drop_column("inspection_capture_receipt", "storage_reference")
    op.drop_column("inspection_capture_receipt", "storage_backend_id")
    op.drop_table("inspection_original_staging")
    op.execute("DROP FUNCTION guard_inspection_staging_receipt()")
