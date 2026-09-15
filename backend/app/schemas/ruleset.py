"""§3 Screen 8 Admin Ruleset Config contract."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class ScheduleIIBandIn(BaseModel):
    max_area_cm2: float | None = Field(
        None, description="Upper bound of PDP area in cm² (null = open-ended top bracket)"
    )
    min_font_mm: float = Field(..., gt=0)
    description: str = Field(..., min_length=1)


class ScheduleIIBandOut(ScheduleIIBandIn):
    pass


class RulesetVersionCreate(BaseModel):
    version: str = Field(..., min_length=1, max_length=200)
    effective_date: date
    is_placeholder: bool = True
    notice: str = Field(..., min_length=1)
    bands: list[ScheduleIIBandIn] = Field(..., min_length=1)

    @field_validator("bands")
    @classmethod
    def exactly_one_open_ended_band(cls, bands: list[ScheduleIIBandIn]) -> list[ScheduleIIBandIn]:
        open_ended = [b for b in bands if b.max_area_cm2 is None]
        if len(open_ended) != 1:
            raise ValueError(
                "bands must contain exactly one open-ended band (max_area_cm2=null) as the final bracket"
            )
        return bands


class RulesetVersionResponse(BaseModel):
    version: str
    effective_date: date
    is_placeholder: bool
    notice: str
    bands: list[ScheduleIIBandOut]
    is_active: bool
    created_by_id: uuid.UUID | None
    created_at: datetime


class RulesetVersionListResponse(BaseModel):
    versions: list[RulesetVersionResponse]
