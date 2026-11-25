"""Fence expired upload reservations before deleting unfinalized originals."""
from alembic import op
import sqlalchemy as sa


revision = "028_inspection_storage_fence"
down_revision = "027_inspection_submission"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inspection_upload_tombstone",
        sa.Column("reservation_id", sa.Uuid(),
                  sa.ForeignKey("inspection_upload_reservation.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute("""
        CREATE TRIGGER inspection_upload_tombstone_immutable
        BEFORE UPDATE OR DELETE ON inspection_upload_tombstone
        FOR EACH ROW EXECUTE FUNCTION guard_inspection_capture_identity()
    """)


def downgrade():
    op.drop_table("inspection_upload_tombstone")
