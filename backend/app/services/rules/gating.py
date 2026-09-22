from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from app.models.enums import RuleStatus, ScanStatus
from app.services.rules.evaluators import RuleEvaluationResult
from app.services.vision.semantic.base import MANDATED_SCHEMA_FIELDS, ExtractedFieldResult

logger = logging.getLogger(__name__)

# Statutory thresholds per Blueprint §6.1
MIN_OCR_CONFIDENCE_THRESHOLD: float = 0.95
MIN_SEMANTIC_CONFIDENCE_THRESHOLD: float = 0.90


class FieldVerificationStatus(str, Enum):
    """
    Per-field verification state per §6.1.
    If OCR confidence < 0.95 or semantic confidence < 0.90, the field is UNVERIFIED.
    """
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"


def gate_field(field: ExtractedFieldResult | Any | None) -> FieldVerificationStatus:
    """
    Evaluates per-field confidence gating per §6.1:
    ```python
    def gate_field(field):
        if field.ocr_confidence < 0.95 or field.semantic_confidence < 0.90:
            return UNVERIFIED
        return VERIFIED
    ```
    """
    if field is None:
        return FieldVerificationStatus.UNVERIFIED

    ocr_conf = getattr(field, "ocr_confidence", None)
    sem_conf = getattr(field, "semantic_confidence", None)

    if ocr_conf is None or sem_conf is None:
        return FieldVerificationStatus.UNVERIFIED

    if ocr_conf < MIN_OCR_CONFIDENCE_THRESHOLD or sem_conf < MIN_SEMANTIC_CONFIDENCE_THRESHOLD:
        return FieldVerificationStatus.UNVERIFIED

    return FieldVerificationStatus.VERIFIED


def gate_fields(fields: dict[str, ExtractedFieldResult]) -> dict[str, FieldVerificationStatus]:
    """Applies gate_field across all extracted declaration fields."""
    return {name: gate_field(field) for name, field in fields.items()}


def rollup_scan_status(
    rule_results: list[RuleEvaluationResult],
    fields: dict[str, ExtractedFieldResult] | None = None,
    calibration_status: ScanStatus = ScanStatus.QUEUED,
) -> ScanStatus:
    """
    Scan-level status rollup logic exactly per §6.1 of the blueprint:

    1. Calibration hard-gates (§4.3 Step 1 & Step 3):
       - CALIBRATION_FAILED: Reference card missing or confidence < 0.85.
       - LOW_CONFIDENCE_CALIBRATION: Dual-edge ratio discrepancy > 5%.

    2. Legal Metrology PCR 2011 compliance rollup (§6.1):
       - FAILED: At least one VERIFIED field breaks a rule (or mandatory declaration missing).
       - PENDING_REVIEW: No VERIFIED failures, but at least one field or rule is UNVERIFIED.
       - PASSED: All mandatory fields are VERIFIED and all rules pass.
    """
    # Calibration gating has strict precedence: do not evaluate pass/fail if reference object was unverified
    if calibration_status == ScanStatus.CALIBRATION_FAILED:
        return ScanStatus.CALIBRATION_FAILED

    if calibration_status == ScanStatus.LOW_CONFIDENCE_CALIBRATION:
        return ScanStatus.LOW_CONFIDENCE_CALIBRATION

    # Check for any rule failures
    if any(r.status == RuleStatus.FAIL for r in rule_results):
        return ScanStatus.FAILED

    # Check for any rule unverified outcomes (caused by low OCR or semantic confidence)
    if any(r.status == RuleStatus.UNVERIFIED for r in rule_results):
        return ScanStatus.PENDING_REVIEW

    # Check if any *mandated* declaration failed confidence gating.  Indicative
    # fields (product_name, declared_dimensions) never route a scan to review.
    if fields is not None and any(
        gate_field(f) == FieldVerificationStatus.UNVERIFIED
        for name, f in fields.items()
        if name in MANDATED_SCHEMA_FIELDS
    ):
        return ScanStatus.PENDING_REVIEW

    # All mandatory fields verified and all rules pass
    return ScanStatus.PASSED
