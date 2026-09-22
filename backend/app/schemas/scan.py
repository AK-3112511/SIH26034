import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import RuleStatus, ScanSource, ScanStatus
from app.schemas.common import SignedFileUrl


class ScanIngestResponse(BaseModel):
    scan_id: uuid.UUID
    status: ScanStatus
    image_url: SignedFileUrl
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
    image_url: SignedFileUrl
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
    captured_by_id: uuid.UUID | None = None
    assigned_lmo_id: uuid.UUID | None = None
    reviewer_note: str | None = None
    product_name: str | None = None
    platform: str | None = None
    reference_object_type: str | None = None
    processing_error: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ScanListItem(BaseModel):
    """Compact scan summary for Review Queue list view."""
    scan_id: uuid.UUID
    source: ScanSource
    status: ScanStatus
    image_url: SignedFileUrl
    lat: float | None = None
    lng: float | None = None
    captured_at_utc: datetime | None = None
    created_at: datetime
    # Derived convenience fields populated server-side
    product_name: str | None = None    # scan.product_name, else extracted brand/manufacturer
    net_quantity: str | None = None
    district_label: str | None = None  # from capturing officer or GPS heuristic
    # Confidence gap: max(ocr_confidence) - min(ocr_confidence) across extracted fields
    confidence_gap: float | None = None
    age_hours: float | None = None     # hours since created_at

    model_config = ConfigDict(from_attributes=True)


class ScanListResponse(BaseModel):
    items: list[ScanListItem]
    total: int
    page: int
    page_size: int


class ReviewSubmitRequest(BaseModel):
    """Body for POST /scans/{scan_id}/review."""
    decision: ScanStatus           # must be PASSED or FAILED
    reviewer_note: str             # mandatory — cannot be empty
    overridden_fields: dict[str, str] | None = None  # field_name → corrected value

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


class HashVerificationResponse(BaseModel):
    scan_id: uuid.UUID
    is_valid: bool
    expected_hash: str
    computed_hash: str


class AssignedScanItem(BaseModel):
    """Assigned scan/task representation for mobile field LMO per §5.3."""
    scan_id: uuid.UUID
    source: ScanSource
    status: ScanStatus
    image_url: SignedFileUrl
    product_name: str | None = None
    platform: str | None = None
    task_type: str = "field_followup"
    assigned_at_utc: datetime | None = None
    reviewer_note: str | None = None
    instructions: str | None = None
    rule_violations: list[str] = []

    model_config = ConfigDict(from_attributes=True)

