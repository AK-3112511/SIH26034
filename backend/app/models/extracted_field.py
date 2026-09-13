from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.scan import Scan

class ExtractedField(Base):
    __tablename__ = "extracted_fields"

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
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    bbox: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    semantic_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    font_height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    scan: Mapped[Scan] = relationship("Scan", back_populates="extracted_fields")

    __table_args__ = (
        Index("idx_extracted_fields_bbox", "bbox", postgresql_using="gin"),
    )
