from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, Text, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ScanSource, ScanStatus

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
        ENUM(ScanSource, name="scan_source_enum", create_type=False),
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
        ENUM(ScanStatus, name="scan_status_enum", create_type=False),
        nullable=False
    )
    ruleset_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

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
