"""End-to-end scan processing.

``MasterPipeline`` chains the vision and rule stages for one image;
``process_scan`` wraps it with persistence, state transitions and events for a
stored scan record.

State machine for a scan while it is processed::

    QUEUED ──► PROCESSING ──► PASSED | FAILED | PENDING_REVIEW
                    │           | CALIBRATION_FAILED | LOW_CONFIDENCE_CALIBRATION
                    └──► PROCESSING_FAILED   (unexpected error; reason stored)

A scan can be (re)processed from QUEUED, PROCESSING_FAILED, CALIBRATION_FAILED
and LOW_CONFIDENCE_CALIBRATION.  Nothing is ever left in QUEUED/PROCESSING
after a crash: the failure is recorded on the row.
"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_session_factory
from app.models.enums import ScanStatus
from app.models.extracted_field import ExtractedField
from app.models.rule_result import RuleResult
from app.models.scan import Scan
from app.services.audit import log_status_change
from app.services.district import resolve_district_label
from app.services.events import emit_scan_status_changed
from app.services.rules.engine import (
    ComplianceRuleEngine,
    ScanComplianceEvaluation,
    persist_rule_results,
)
from app.services.rules.gating import rollup_scan_status
from app.services.storage import get_storage_provider
from app.services.vision.extraction_pipeline import (
    ExtractionPipeline,
    ExtractionResult,
    get_extraction_pipeline,
)
from app.services.vision.preprocessor import (
    PreprocessingPipeline,
    PreprocessingResult,
)
from app.services.vision.semantic.base import ExtractedFieldResult
from app.services.vision.spatial_calibration import (
    SpatialCalibrationService,
    SpatialMeasurementResult,
)

logger = logging.getLogger(__name__)

# Statuses from which (re)processing is allowed.
REPROCESSABLE_STATUSES = (
    ScanStatus.QUEUED,
    ScanStatus.PROCESSING_FAILED,
    ScanStatus.CALIBRATION_FAILED,
    ScanStatus.LOW_CONFIDENCE_CALIBRATION,
)

# A scan stuck in PROCESSING longer than this is considered orphaned (the
# worker died) and is re-queued at startup.
STALE_PROCESSING_AFTER = timedelta(minutes=15)

# Vision inference is CPU-bound; more parallel scans than cores only thrash.
_PROCESSING_SLOTS = threading.BoundedSemaphore(max(1, settings.PIPELINE_MAX_CONCURRENCY))

# The OCR models take seconds to load, so one extraction pipeline is shared
# for the life of the process.
_SHARED_EXTRACTION: ExtractionPipeline | None = None
_SHARED_LOCK = threading.Lock()


def get_shared_extraction_pipeline() -> ExtractionPipeline:
    global _SHARED_EXTRACTION
    with _SHARED_LOCK:
        if _SHARED_EXTRACTION is None:
            _SHARED_EXTRACTION = get_extraction_pipeline()
        return _SHARED_EXTRACTION


def warm_up_engines() -> None:
    """Load vision models ahead of the first scan (called from app startup)."""
    pipeline = get_shared_extraction_pipeline()
    warm = getattr(pipeline.ocr_engine, "warm_up", None)
    if callable(warm):
        ok = warm()
        logger.info("OCR engine warm-up %s (%s)", "complete" if ok else "FAILED", type(pipeline.ocr_engine).__name__)


@dataclass
class PipelineExecutionResult:
    """Complete diagnostic and analytical output of the full MetrologyAI pipeline."""

    status: ScanStatus
    preprocessing: PreprocessingResult
    extraction: ExtractionResult | None = None
    spatial: SpatialMeasurementResult | None = None
    compliance: ScanComplianceEvaluation | None = None
    fields: dict[str, ExtractedFieldResult] = field(default_factory=dict)
    pdp_area_cm2: float | None = None
    mm_per_px: float | None = None
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "preprocessing": self.preprocessing.to_dict(),
            "extraction": self.extraction.to_dict() if self.extraction else None,
            "spatial": self.spatial.to_dict() if self.spatial else None,
            "compliance": self.compliance.to_dict() if self.compliance else None,
            "pdp_area_cm2": self.pdp_area_cm2,
            "mm_per_px": self.mm_per_px,
            "failure_reason": self.failure_reason,
        }


class MasterPipeline:
    """Vision + rule evaluation for a single image.

    1. Preprocessing — reference-card detection and gating, perspective
       correction, cylindrical dewarp, CLAHE (or the manual-dimension path).
    2. Extraction — OCR and semantic mapping to the mandated declarations.
    3. Spatial calibration — mm/px cross-check, numeral heights, PDP area.
    4. Rule engine and confidence gating — PCR 2011 verdict rollup.
    """

    def __init__(
        self,
        preprocessor: PreprocessingPipeline | None = None,
        extraction_pipeline: ExtractionPipeline | None = None,
        spatial_service: SpatialCalibrationService | None = None,
        rule_engine: ComplianceRuleEngine | None = None,
        db: Session | None = None,
    ) -> None:
        self.preprocessor = preprocessor or PreprocessingPipeline()
        self.extraction_pipeline = extraction_pipeline or get_shared_extraction_pipeline()
        self.spatial_service = spatial_service or SpatialCalibrationService()
        # Resolves the admin-activated ruleset version from the DB when available.
        self.rule_engine = rule_engine or ComplianceRuleEngine(db=db)

    def execute(
        self,
        image: np.ndarray,
        reference_object_type: str | None = None,
        product_type: str | None = None,
        manual_mm_per_px: float | None = None,
        manual_pdp_area_cm2: float | None = None,
    ) -> PipelineExecutionResult:
        """Run every stage against a raw BGR image."""
        preproc_result = self.preprocessor.process(
            image,
            reference_object_type=reference_object_type,
            product_type=product_type,
            manual_mm_per_px=manual_mm_per_px,
            manual_pdp_area_cm2=manual_pdp_area_cm2,
        )

        if preproc_result.status == ScanStatus.CALIBRATION_FAILED:
            logger.warning("Pipeline halted at preprocessing: %s", preproc_result.failure_reason)
            return PipelineExecutionResult(
                status=ScanStatus.CALIBRATION_FAILED,
                preprocessing=preproc_result,
                failure_reason=preproc_result.failure_reason or "Reference card not detected with required confidence",
            )
        if preproc_result.status == ScanStatus.LOW_CONFIDENCE_CALIBRATION:
            logger.warning("Pipeline flagged LOW_CONFIDENCE_CALIBRATION: %s", preproc_result.failure_reason)
            return PipelineExecutionResult(
                status=ScanStatus.LOW_CONFIDENCE_CALIBRATION,
                preprocessing=preproc_result,
                failure_reason=preproc_result.failure_reason or "Spatial ratio cross-check discrepancy exceeded 5%",
            )

        # Extraction runs on the enhanced package face; boxes are translated back
        # to the original image so they can be overlaid on the untouched evidence.
        face = preproc_result.dewarped_package_image
        if face is None or face.size == 0:
            face = image
        origin = (0, 0)
        pkg = preproc_result.package_face_bbox
        if pkg is not None and face is not image:
            # Flat faces are plain crops, so boxes map back exactly.  Unrolled
            # (cylindrical) faces are a remap, so the offset is approximate and
            # glyph heights are measured on the unrolled image itself.
            origin = (pkg.x_min, pkg.y_min)
        extraction_result = self.extraction_pipeline.process(face, origin=origin)

        measure_on = face if (preproc_result.is_cylindrical or preproc_result.clahe_applied) else image
        spatial_result = self.spatial_service.calibrate_and_measure(
            preproc_result=preproc_result,
            extraction_result=extraction_result,
            source_image=measure_on,
            measurement_origin=origin if measure_on is face else (0, 0),
        )
        calib_status = spatial_result.calibration.status

        qty_field = spatial_result.fields.get("net_quantity")
        font_height_mm = qty_field.font_height_mm if qty_field else None

        compliance_eval = self.rule_engine.evaluate(
            fields=spatial_result.fields,
            font_height_mm=font_height_mm,
            pdp_area_cm2=spatial_result.pdp_area_cm2,
            calibration_status=calib_status,
        )
        final_status = rollup_scan_status(
            rule_results=compliance_eval.rule_results,
            fields=spatial_result.fields,
            calibration_status=calib_status,
        )

        return PipelineExecutionResult(
            status=final_status,
            preprocessing=preproc_result,
            extraction=extraction_result,
            spatial=spatial_result,
            compliance=compliance_eval,
            fields=spatial_result.fields,
            pdp_area_cm2=spatial_result.pdp_area_cm2,
            mm_per_px=spatial_result.calibration.mm_per_px,
            failure_reason=spatial_result.calibration.reason if not spatial_result.calibration.is_consistent else None,
        )


# ---------------------------------------------------------------------------
# Persistence wrapper
# ---------------------------------------------------------------------------

def _mark_failed(db: Session, scan: Scan, old_status: str, status: ScanStatus, reason: str) -> None:
    scan.status = status
    scan.processing_error = reason[:2000]
    log_status_change(
        db=db,
        target_type="scan",
        target_id=str(scan.scan_id),
        new_status=status.value,
        old_status=old_status,
        detail={"error": reason[:500]},
    )
    db.commit()


def _persist_fields(db: Session, scan: Scan, fields: dict[str, ExtractedFieldResult]) -> None:
    """Replace the scan's extracted fields with the latest run's output."""
    existing = {ef.field_name: ef for ef in db.query(ExtractedField).filter(ExtractedField.scan_id == scan.scan_id)}
    for field_name, f_res in fields.items():
        row = existing.pop(field_name, None)
        if row is None:
            row = ExtractedField(scan_id=scan.scan_id, field_name=field_name)
            db.add(row)
        row.raw_text = f_res.raw_text
        row.bbox = f_res.bbox
        row.ocr_confidence = f_res.ocr_confidence
        row.semantic_confidence = f_res.semantic_confidence
        row.font_height_mm = f_res.font_height_mm
    # Fields from a previous run that this run did not find are stale evidence.
    for stale in existing.values():
        if stale.field_name != "declared_dimensions":
            db.delete(stale)


def process_scan(
    scan_id: uuid.UUID,
    db: Session | None = None,
    pipeline: MasterPipeline | None = None,
) -> Scan | None:
    """Run the full pipeline for one stored scan and persist the outcome."""
    should_close_db = False
    if db is None:
        db = get_session_factory()()
        should_close_db = True

    try:
        scan = db.query(Scan).filter(Scan.scan_id == scan_id).first()
        if not scan:
            logger.error("process_scan: scan %s not found in database", scan_id)
            return None
        if scan.status not in REPROCESSABLE_STATUSES:
            logger.info("process_scan: scan %s is %s; not reprocessing", scan_id, scan.status.value)
            return scan

        old_status = scan.status.value
        scan.status = ScanStatus.PROCESSING
        scan.processing_error = None
        db.commit()

        with _PROCESSING_SLOTS:
            try:
                return _run_and_persist(db, scan, old_status, pipeline)
            except Exception as exc:  # never leave a scan stuck in PROCESSING
                logger.exception("process_scan: unexpected failure for scan %s", scan_id)
                db.rollback()
                scan = db.query(Scan).filter(Scan.scan_id == scan_id).first()
                if scan is not None:
                    _mark_failed(db, scan, old_status, ScanStatus.PROCESSING_FAILED, f"{type(exc).__name__}: {exc}")
                return scan
    finally:
        if should_close_db:
            db.close()


def _run_and_persist(db: Session, scan: Scan, old_status: str, pipeline: MasterPipeline | None) -> Scan:
    storage = get_storage_provider()
    try:
        image_bytes = storage.get_file(scan.image_url)
    except Exception as exc:
        _mark_failed(db, scan, old_status, ScanStatus.PROCESSING_FAILED, f"Evidence image unavailable in storage: {exc}")
        return scan

    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        _mark_failed(db, scan, old_status, ScanStatus.PROCESSING_FAILED, "Image decode error: stored bytes are not a valid image")
        return scan

    manual_mm_per_px = scan.mm_per_px if scan.reference_object_type == "manual" else None
    manual_pdp = scan.pdp_area_cm2 if manual_mm_per_px is not None else None

    active_pipeline = pipeline or MasterPipeline(db=db)
    result = active_pipeline.execute(
        image=image,
        reference_object_type=scan.reference_object_type,
        product_type=scan.product_type,
        manual_mm_per_px=manual_mm_per_px,
        manual_pdp_area_cm2=manual_pdp,
    )

    _persist_fields(db, scan, result.fields)
    if result.compliance:
        persist_rule_results(db=db, scan_id=scan.scan_id, evaluation=result.compliance)
        scan.ruleset_version = result.compliance.ruleset_version
    else:
        db.query(RuleResult).filter(RuleResult.scan_id == scan.scan_id).delete()

    scan.status = result.status
    if manual_mm_per_px is None:
        scan.mm_per_px = result.mm_per_px
        scan.pdp_area_cm2 = result.pdp_area_cm2
    scan.processing_error = result.failure_reason
    if scan.product_name is None:
        extracted_name = result.fields.get("product_name")
        if extracted_name and extracted_name.raw_text:
            scan.product_name = extracted_name.raw_text[:200]

    log_status_change(
        db=db,
        target_type="scan",
        target_id=str(scan.scan_id),
        new_status=result.status.value,
        old_status=old_status,
        detail={
            "notes": f"Automated pipeline execution completed: {result.status.value}",
            "ocr_engine": result.extraction.ocr_engine_name if result.extraction else None,
            "semantic_engine": result.extraction.semantic_engine_name if result.extraction else None,
            "detector": result.preprocessing.detection_result.engine if result.preprocessing.detection_result else None,
            "card_confidence": (
                result.preprocessing.reference_card_bbox.confidence if result.preprocessing.reference_card_bbox else None
            ),
            "mm_per_px": scan.mm_per_px,
            "pdp_area_cm2": scan.pdp_area_cm2,
            "failure_reason": result.failure_reason,
        },
    )
    db.commit()
    db.refresh(scan)

    rule_summaries = [
        {"rule_id": r.rule_id, "status": getattr(r.status, "value", str(r.status)), "reason": r.reason}
        for r in (result.compliance.rule_results if result.compliance else [])
    ]
    try:
        emit_scan_status_changed(
            db=db,
            scan_id=scan.scan_id,
            new_status=scan.status.value,
            rule_results=rule_summaries,
            assigned_lmo_id=scan.captured_by_id or scan.assigned_lmo_id,
            district=resolve_district_label(scan, db),
        )
    except Exception as event_err:
        logger.warning("Failed to emit scan.status_changed event for %s: %s", scan.scan_id, event_err)

    logger.info("process_scan: scan %s -> %s", scan.scan_id, scan.status.value)
    return scan


def process_queued_scans(
    limit: int = 10,
    db: Session | None = None,
    pipeline: MasterPipeline | None = None,
) -> list[Scan]:
    """Process pending QUEUED scans (oldest first), up to ``limit``."""
    should_close_db = False
    if db is None:
        db = get_session_factory()()
        should_close_db = True

    try:
        queued = (
            db.query(Scan)
            .filter(Scan.status == ScanStatus.QUEUED)
            .order_by(Scan.created_at.asc())
            .limit(limit)
            .all()
        )
        processed: list[Scan] = []
        for s in queued:
            res = process_scan(scan_id=s.scan_id, db=db, pipeline=pipeline)
            if res:
                processed.append(res)
        return processed
    finally:
        if should_close_db:
            db.close()


def requeue_stale_processing(db: Session | None = None) -> int:
    """Return scans orphaned in PROCESSING by a previous worker crash to QUEUED."""
    should_close_db = False
    if db is None:
        db = get_session_factory()()
        should_close_db = True
    try:
        cutoff = datetime.now(timezone.utc) - STALE_PROCESSING_AFTER
        stale = db.query(Scan).filter(Scan.status == ScanStatus.PROCESSING, Scan.created_at < cutoff).all()
        for scan in stale:
            scan.status = ScanStatus.QUEUED
            scan.processing_error = "Re-queued after an interrupted processing run"
        if stale:
            db.commit()
            logger.warning("Re-queued %d scan(s) orphaned in PROCESSING", len(stale))
        return len(stale)
    finally:
        if should_close_db:
            db.close()
