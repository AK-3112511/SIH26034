"""Core evidence record: one row per captured package (mobile) or listing (e-commerce)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ScanSource, ScanStatus, enum_values

if TYPE_CHECKING:
    from app.models.challan import Challan
    from app.models.extracted_field import ExtractedField
    from app.models.rule_result import RuleResult

class Scan(Base):
    __tablename__ = "scans"

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    source: Mapped[ScanSource] = mapped_column(
        ENUM(ScanSource, name="scan_source_enum", create_type=False, values_callable=enum_values),
        nullable=False
    )
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    location: Mapped[str | None] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True),
        nullable=True
    )
    captured_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    mm_per_px: Mapped[float | None] = mapped_column(Float, nullable=True)
    pdp_area_cm2: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[ScanStatus] = mapped_column(
        ENUM(ScanStatus, name="scan_status_enum", create_type=False, values_callable=enum_values),
        nullable=False
    )
    ruleset_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    # Officer who captured/uploaded the evidence (chain of custody).
    captured_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Field officer assigned for follow-up (e-commerce → field loop).
    assigned_lmo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Mandatory reviewer note when submitting a decision.
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Human-readable product identity (manual entry or extracted brand line).
    product_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    # E-commerce platform tag (Blinkit, Amazon, ...); null for mobile captures.
    platform: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Reference object the officer placed next to the product (debit_card | pan_card | manual).
    reference_object_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Container type hint for the curvature heuristic (box | bottle | other).
    product_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Why processing failed / calibration failed, shown to reviewers.
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    extracted_fields: Mapped[list[ExtractedField]] = relationship(
        "ExtractedField",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    rule_results: Mapped[list[RuleResult]] = relationship(
        "RuleResult",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    challans: Mapped[list[Challan]] = relationship(
        "Challan",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
