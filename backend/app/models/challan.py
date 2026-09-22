from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.scan import Scan

class Challan(Base):
    __tablename__ = "challans"

    challan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.scan_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    lmo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    scan: Mapped[Scan] = relationship("Scan", back_populates="challans")

    __table_args__ = (
        # One Section 39 notice per scan — regeneration returns the existing record.
        UniqueConstraint("scan_id", name="uq_challans_scan"),
    )
