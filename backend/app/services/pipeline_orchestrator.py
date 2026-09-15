from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models.enums import ScanStatus
from app.models.extracted_field import ExtractedField
from app.models.scan import Scan
from app.services.audit import log_status_change
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


@dataclass
class PipelineExecutionResult:
    """Complete diagnostic and analytical output of the full MetrologyAI pipeline (Phases 3.1 -> 3.5)."""
    status: ScanStatus
    preprocessing: PreprocessingResult
    extraction: ExtractionResult | None = None
    spatial: SpatialMeasurementResult | None = None
    compliance: ScanComplianceEvaluation | None = None
    fields: dict[str, ExtractedFieldResult] = field(default_factory=dict)
    pdp_area_cm2: float | None = None
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "preprocessing": self.preprocessing.to_dict(),
            "extraction": self.extraction.to_dict() if self.extraction else None,
            "spatial": self.spatial.to_dict() if self.spatial else None,
            "compliance": self.compliance.to_dict() if self.compliance else None,
            "pdp_area_cm2": self.pdp_area_cm2,
            "failure_reason": self.failure_reason,
        }


class MasterPipeline:
    """
    End-to-End MetrologyAI Vision & Rule Evaluation Pipeline (§4.3 & §6.1).
    Chains:
    1. Preprocessing (OpenCV dewarp, CLAHE, YOLOv8 reference card gating) -> §4.3 Steps 1-2
    2. Extraction (PaddleOCR + Florence-2 / Rule-based semantic mapping) -> §4.3 Steps 4-5
    3. Spatial Calibration (Dual-edge ratio cross-check, font-to-mm, PDP area) -> §4.3 Steps 3, 6, 7
    4. Legal Metrology PCR 2011 Compliance Rule Engine & Confidence Gating -> §5.1 & §6.1
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
        self.extraction_pipeline = extraction_pipeline or get_extraction_pipeline()
        self.spatial_service = spatial_service or SpatialCalibrationService()
        # Phase 6.3: resolves the admin-activated ruleset version from the DB
        # when available, so activating a new version takes effect on the
        # next scan processed without a code deploy.
        self.rule_engine = rule_engine or ComplianceRuleEngine(db=db)

    def execute(
        self,
        image: np.ndarray,
        reference_object_type: str | None = None,
    ) -> PipelineExecutionResult:
        """
        Executes the full pipeline stages sequentially against a raw BGR image.
        """
        # Step 1: Preprocessing & Reference Card Gating (§4.3 Steps 1-2)
        preproc_result = self.preprocessor.process(image, reference_object_type=reference_object_type)

        # Halt if calibration failed (card confidence < 0.85 or invalid image)
        if preproc_result.status == ScanStatus.CALIBRATION_FAILED:
            logger.warning("Pipeline halted at Step 1: %s", preproc_result.failure_reason)
            return PipelineExecutionResult(
                status=ScanStatus.CALIBRATION_FAILED,
                preprocessing=preproc_result,
                failure_reason=preproc_result.failure_reason or "Reference card not detected with required confidence",
            )
        elif preproc_result.status == ScanStatus.LOW_CONFIDENCE_CALIBRATION:
            logger.warning("Pipeline flagged LOW_CONFIDENCE_CALIBRATION at Step 1: %s", preproc_result.failure_reason)
            return PipelineExecutionResult(
                status=ScanStatus.LOW_CONFIDENCE_CALIBRATION,
                preprocessing=preproc_result,
                failure_reason=preproc_result.failure_reason or "Spatial ratio cross-check discrepancy exceeded 5%",
            )

        # Step 2: OCR & Semantic Extraction (§4.3 Steps 4-5)
        package_face = (
            preproc_result.dewarped_package_image
            if preproc_result.dewarped_package_image is not None and preproc_result.dewarped_package_image.size > 0
            else image
        )
        extraction_result = self.extraction_pipeline.process(package_face)

        # Step 3: Spatial Calibration & Dual-Edge Ratio Cross-Check (§4.3 Steps 3, 6, 7)
        spatial_result = self.spatial_service.calibrate_and_measure(
            preproc_result=preproc_result,
            extraction_result=extraction_result,
        )

        calib_status = spatial_result.calibration.status

        # Step 4: PCR 2011 Compliance Rule Engine & Confidence Gating (§5.1 & §6.1)
        # Determine font height of net_quantity for Schedule II font checking
        qty_field = spatial_result.fields.get("net_quantity")
        font_height_mm = qty_field.font_height_mm if qty_field else None

        compliance_eval = self.rule_engine.evaluate(
            fields=spatial_result.fields,
            font_height_mm=font_height_mm,
            pdp_area_cm2=spatial_result.pdp_area_cm2,
            calibration_status=calib_status,
        )

        # Final Scan-Level Rollup Status
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
        )


def process_scan(
    scan_id: uuid.UUID,
    db: Session | None = None,
    pipeline: MasterPipeline | None = None,
) -> Scan | None:
    """
    Executes the full pipeline for an individual scan identified by scan_id.
    Pulls original immutable image from storage provider, runs Steps 3.1 -> 3.5,
    persists extracted fields and individual rule results, and updates the scan status.
    """
    should_close_db = False
    if db is None:
        db = get_session_factory()()
        should_close_db = True

    try:
        scan = db.query(Scan).filter(Scan.scan_id == scan_id).first()
        if not scan:
            logger.error("process_scan: scan %s not found in database", scan_id)
            return None

        # Only process QUEUED scans (or retry failed calibration if re-triggered)
        if scan.status not in (ScanStatus.QUEUED, ScanStatus.CALIBRATION_FAILED, ScanStatus.LOW_CONFIDENCE_CALIBRATION):
            logger.info("process_scan: scan %s already in definitive status %s; skipping", scan_id, scan.status.value)
            return scan

        old_status = scan.status.value

        # Retrieve image bytes from storage
        storage = get_storage_provider()
        try:
            image_bytes = storage.get_file(scan.image_url)
        except Exception as e:
            logger.exception("process_scan: failed to retrieve image bytes from storage")
            scan.status = ScanStatus.CALIBRATION_FAILED
            log_status_change(
                db=db,
                target_type="scan",
                target_id=str(scan.scan_id),
                new_status=ScanStatus.CALIBRATION_FAILED.value,
                old_status=old_status,
                detail={"error": str(e)},
            )
            db.commit()
            return scan

        # Decode image using OpenCV
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if image is None or image.size == 0:
            logger.error("process_scan: failed to decode image bytes into valid pixel array for scan %s", scan_id)
            scan.status = ScanStatus.CALIBRATION_FAILED
            log_status_change(
                db=db,
                target_type="scan",
                target_id=str(scan.scan_id),
                new_status=ScanStatus.CALIBRATION_FAILED.value,
                old_status=old_status,
                detail={"error": "Image decode error: file bytes did not produce a valid BGR image"},
            )
            db.commit()
            return scan

        # Execute Master Pipeline
        active_pipeline = pipeline or MasterPipeline(db=db)
        result = active_pipeline.execute(image=image)

        # 1. Persist Extracted Fields
        if result.fields:
            for field_name, f_res in result.fields.items():
                # Check existing or create new
                existing_field = (
                    db.query(ExtractedField)
                    .filter(ExtractedField.scan_id == scan.scan_id, ExtractedField.field_name == field_name)
                    .first()
                )
                if existing_field:
                    existing_field.raw_text = f_res.raw_text
                    existing_field.bbox = f_res.bbox
                    existing_field.ocr_confidence = f_res.ocr_confidence
                    existing_field.semantic_confidence = f_res.semantic_confidence
                    existing_field.font_height_mm = f_res.font_height_mm
                else:
                    new_field = ExtractedField(
                        scan_id=scan.scan_id,
                        field_name=field_name,
                        raw_text=f_res.raw_text,
                        bbox=f_res.bbox,
                        ocr_confidence=f_res.ocr_confidence,
                        semantic_confidence=f_res.semantic_confidence,
                        font_height_mm=f_res.font_height_mm,
                    )
                    db.add(new_field)

        # 2. Persist Rule Results (if evaluated)
        if result.compliance:
            persist_rule_results(db=db, scan_id=scan.scan_id, evaluation=result.compliance)
            scan.ruleset_version = result.compliance.ruleset_version

        # 3. Update Scan attributes
        scan.status = result.status
        scan.pdp_area_cm2 = result.pdp_area_cm2

        # 4. Audit Log
        log_status_change(
            db=db,
            target_type="scan",
            target_id=str(scan.scan_id),
            new_status=result.status.value,
            old_status=old_status,
            detail={"notes": f"Automated pipeline execution completed: {result.status.value}"},
        )

        db.commit()
        db.refresh(scan)
        logger.info("process_scan: scan %s processed successfully -> status: %s", scan_id, scan.status.value)
        return scan

    finally:
        if should_close_db:
            db.close()


def process_queued_scans(
    limit: int = 10,
    db: Session | None = None,
    pipeline: MasterPipeline | None = None,
) -> list[Scan]:
    """
    Batch-processes pending QUEUED scans up to limit.
    """
    should_close_db = False
    if db is None:
        db = get_session_factory()()
        should_close_db = True

    try:
        queued_scans = (
            db.query(Scan)
            .filter(Scan.status == ScanStatus.QUEUED)
            .order_by(Scan.created_at.asc())
            .limit(limit)
            .all()
        )

        processed: list[Scan] = []
        for s in queued_scans:
            res = process_scan(scan_id=s.scan_id, db=db, pipeline=pipeline)
            if res:
                processed.append(res)

        return processed
    finally:
        if should_close_db:
            db.close()
