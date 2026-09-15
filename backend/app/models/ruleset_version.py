"""Phase 6.3: persisted, versioned Schedule II ruleset config (§5.1's
"config table, versioned, timestamped" note). Append-only by convention —
no endpoint ever mutates `bands`/`effective_date`/`notice` on an existing
row, only `is_active` toggles and brand-new rows are inserted, so a version
a past challan's `scans.ruleset_version` points to is never silently
overwritten (mirrors how `audit_log` is append-only elsewhere in this app).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RulesetVersion(Base):
    __tablename__ = "ruleset_versions"

    version: Mapped[str] = mapped_column(Text, primary_key=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_placeholder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notice: Mapped[str] = mapped_column(Text, nullable=False)
    # list[{"max_area_cm2": float | None, "min_font_mm": float, "description": str}]
    bands: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
