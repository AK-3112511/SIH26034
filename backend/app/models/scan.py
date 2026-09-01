from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Float, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from app.db.base import Base
from app.models.enums import ScanSource, ScanStatus

if TYPE_CHECKING:
    from app.models.extracted_field import ExtractedField
    from app.models.rule_result import RuleResult
    from app.models.challan import Challan

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
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True),
        nullable=True
    )
    captured_at_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    mm_per_px: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pdp_area_cm2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[ScanStatus] = mapped_column(
        ENUM(ScanStatus, name="scan_status_enum", create_type=False),
        nullable=False
    )
    ruleset_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    extracted_fields: Mapped[List[ExtractedField]] = relationship(
        "ExtractedField",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    rule_results: Mapped[List[RuleResult]] = relationship(
        "RuleResult",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    challans: Mapped[List[Challan]] = relationship(
        "Challan",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
