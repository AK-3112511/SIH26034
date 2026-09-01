import uuid
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict
from app.models.enums import ScanSource, ScanStatus, RuleStatus

class ScanIngestResponse(BaseModel):
    scan_id: uuid.UUID
    status: ScanStatus
    image_url: str
    evidence_hash: str
    captured_at_utc: Optional[datetime] = None
    created_at: datetime
    message: str = "Scan received and queued for processing"

    model_config = ConfigDict(from_attributes=True)


class ExtractedFieldResponse(BaseModel):
    id: uuid.UUID
    field_name: str
    raw_text: Optional[str] = None
    bbox: Optional[Any] = None
    ocr_confidence: Optional[float] = None
    semantic_confidence: Optional[float] = None
    font_height_mm: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class RuleResultResponse(BaseModel):
    id: uuid.UUID
    rule_id: str
    status: RuleStatus
    reason: Optional[str] = None
    evidence: Optional[Any] = None

    model_config = ConfigDict(from_attributes=True)


class ScanDetailResponse(BaseModel):
    scan_id: uuid.UUID
    source: ScanSource
    status: ScanStatus
    image_url: str
    evidence_hash: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    captured_at_utc: Optional[datetime] = None
    mm_per_px: Optional[float] = None
    pdp_area_cm2: Optional[float] = None
    ruleset_version: Optional[str] = None
    created_at: datetime
    extracted_fields: List[ExtractedFieldResponse] = []
    rule_results: List[RuleResultResponse] = []

    model_config = ConfigDict(from_attributes=True)
