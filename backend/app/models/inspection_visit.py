"""Assigned inspection visit for Gate 1."""
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InspectionVisit(Base):
    __tablename__ = "inspection_visit"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_client_id", "tenant_id"], ["clients.client_id", "clients.tenant_id"],
            name="fk_inspection_visit_client_tenant", onupdate="RESTRICT", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["vendor_id", "tenant_id"], ["vendors.vendor_id", "vendors.tenant_id"],
            name="fk_inspection_visit_vendor_tenant", onupdate="RESTRICT", ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_inspection_visit_tenant"),
        CheckConstraint("generation > 0", name="ck_inspection_visit_generation"),
        Index("ix_inspection_visit_owner", "owner_client_id", "tenant_id"),
        Index("ix_inspection_visit_vendor", "vendor_id", "tenant_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant_config.tenant_id", ondelete="RESTRICT"))
    owner_client_id: Mapped[UUID]
    vendor_id: Mapped[str] = mapped_column(String(6))
    assignment_id: Mapped[UUID] = mapped_column(server_default=text("gen_random_uuid()"))
    generation: Mapped[int] = mapped_column(BigInteger, server_default="1")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    package_sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    workflow_version_id: Mapped[UUID | None]
    revision: Mapped[int] = mapped_column(BigInteger, server_default="0")
