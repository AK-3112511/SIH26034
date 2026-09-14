import uuid
from datetime import datetime
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, ConfigDict, field_validator

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

    extracted_fields: List[ExtractedFieldResponse] = []
    rule_results: List[RuleResultResponse] = []
    # Phase 4: reviewer assignment fields
    assigned_lmo_id: Optional[uuid.UUID] = None
    reviewer_note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ScanListItem(BaseModel):
    """Compact scan summary for Review Queue list view."""
    scan_id: uuid.UUID
    source: ScanSource
    status: ScanStatus
    image_url: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    captured_at_utc: Optional[datetime] = None
    created_at: datetime
    # Derived convenience fields populated server-side
    product_name: Optional[str] = None   # from extracted_fields.net_quantity or brand name
    district_label: Optional[str] = None  # from scan or user's district
    # Confidence gap: max(ocr_confidence) - min(ocr_confidence) across extracted fields
    confidence_gap: Optional[float] = None
    age_hours: Optional[float] = None    # hours since created_at

    

    model_config = ConfigDict(from_attributes=True)


class ScanListResponse(BaseModel):
    items: List[ScanListItem]
    total: int
    page: int
    page_size: int


class ReviewSubmitRequest(BaseModel):
    """Body for POST /scans/{scan_id}/review."""
    decision: ScanStatus           # must be PASSED or FAILED
    reviewer_note: str             # mandatory — cannot be empty
    overridden_fields: Optional[Dict[str, str]] = None  # field_name → corrected value

    @field_validator("reviewer_note")
    @classmethod
    def reviewer_note_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("reviewer_note is mandatory and cannot be empty")
        return v.strip()

    @field_validator("decision")
    @classmethod
    def decision_must_be_terminal(cls, v: ScanStatus) -> ScanStatus:
        if v not in (ScanStatus.PASSED, ScanStatus.FAILED):
            raise ValueError("decision must be PASSED or FAILED")
        return v


class ReviewSubmitResponse(BaseModel):
    scan_id: uuid.UUID
    new_status: ScanStatus
    reviewer_note: str
    message: str = "Review submitted successfully"


class DashboardStatsResponse(BaseModel):
    """Today's overview counts for the Overview screen."""
    scanned_today: int
    passed_today: int
    failed_today: int
    pending_review: int   # total queue depth, not just today's
    calibration_failed_today: int


class IngestDerivedRequest(BaseModel):
    """E-commerce ingestion: manual dimensions replace reference card calibration."""
    declared_net_quantity: Optional[str] = None
    package_height_mm: float
    package_width_mm: float
    package_depth_mm: Optional[float] = None
    platform: str          # 'blinkit' | 'amazon' | 'flipkart' | 'other'
    platform_url: Optional[str] = None


class HashVerificationResponse(BaseModel):
    scan_id: uuid.UUID
    is_valid: bool
    expected_hash: str
    computed_hash: str
