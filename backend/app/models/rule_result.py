from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RuleStatus

if TYPE_CHECKING:
    from app.models.scan import Scan

class RuleResult(Base):
    __tablename__ = "rule_results"

    id: Mapped[uuid.UUID] = mapped_column(
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
    rule_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RuleStatus] = mapped_column(
        ENUM(RuleStatus, name="rule_status_enum", create_type=False),
        nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[Any | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    scan: Mapped[Scan] = relationship("Scan", back_populates="rule_results")

    __table_args__ = (
        UniqueConstraint("scan_id", "rule_id", name="uq_rule_results_scan_rule"),
        Index("idx_rule_results_evidence", "evidence", postgresql_using="gin"),
    )
