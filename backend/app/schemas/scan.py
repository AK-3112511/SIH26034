import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import RuleStatus, ScanSource, ScanStatus


class ScanIngestResponse(BaseModel):
    scan_id: uuid.UUID
    status: ScanStatus
    image_url: str
    evidence_hash: str
    captured_at_utc: datetime | None = None
    created_at: datetime
    message: str = "Scan received and queued for processing"

    model_config = ConfigDict(from_attributes=True)


class ExtractedFieldResponse(BaseModel):
    id: uuid.UUID
    field_name: str
    raw_text: str | None = None
    bbox: Any | None = None
    ocr_confidence: float | None = None
    semantic_confidence: float | None = None
    font_height_mm: float | None = None

    model_config = ConfigDict(from_attributes=True)


class RuleResultResponse(BaseModel):
    id: uuid.UUID
    rule_id: str
    status: RuleStatus
    reason: str | None = None
    evidence: Any | None = None

    model_config = ConfigDict(from_attributes=True)


class ScanDetailResponse(BaseModel):
    scan_id: uuid.UUID
    source: ScanSource
    status: ScanStatus
    image_url: str
    evidence_hash: str
    lat: float | None = None
    lng: float | None = None
    captured_at_utc: datetime | None = None
    mm_per_px: float | None = None
    pdp_area_cm2: float | None = None
    ruleset_version: str | None = None
    created_at: datetime
    extracted_fields: list[ExtractedFieldResponse] = []
    rule_results: list[RuleResultResponse] = []

    model_config = ConfigDict(from_attributes=True)
