from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from app.models.enums import ScanStatus
from app.services.vision.detector import BoundingBox
from app.services.vision.extraction_pipeline import ExtractionResult
from app.services.vision.perspective import (
    ISO_CARD_HEIGHT_MM,
    ISO_CARD_WIDTH_MM,
    order_quad_corners,
)
from app.services.vision.semantic.base import ExtractedFieldResult

if TYPE_CHECKING:
    from app.services.vision.preprocessor import PreprocessingResult

logger = logging.getLogger(__name__)

# Mandatory maximum allowable discrepancy between long-edge and short-edge ratios (§4.3 Step 3)
MAX_RATIO_DISCREPANCY_THRESHOLD = 0.05  # 5.0%


@dataclass
class CalibrationMetrics:
    """
    Encapsulates the mathematical dual-edge spatial calibration metrics per §4.2 & §4.3 (Step 3).
    """
    ratio_short: float          # mm/px derived from 53.98mm short edge
    ratio_long: float           # mm/px derived from 85.60mm long edge
    mm_per_px: float | None     # Authoritative scale factor (None if calibration failed or rejected)
    discrepancy_pct: float      # Relative discrepancy between long and short ratios
    is_consistent: bool         # True if discrepancy <= 5.0%
    status: ScanStatus          # QUEUED, LOW_CONFIDENCE_CALIBRATION, or CALIBRATION_FAILED
    reason: str | None = None   # Audit explanation if low confidence or failed

    def to_dict(self) -> dict[str, Any]:
        return {
            "ratio_short": round(self.ratio_short, 6),
            "ratio_long": round(self.ratio_long, 6),
            "mm_per_px": round(self.mm_per_px, 6) if self.mm_per_px is not None else None,
            "discrepancy_pct": round(self.discrepancy_pct * 100.0, 2),
            "is_consistent": self.is_consistent,
            "status": self.status.value,
            "reason": self.reason,
        }


@dataclass
class SpatialMeasurementResult:
    """
    Encapsulates real-world metric dimensions (font heights, PDP area, container dimensions)
    derived from spatial calibration.
    """
    calibration: CalibrationMetrics
    pdp_area_cm2: float | None
    fields: dict[str, ExtractedFieldResult]
    package_width_mm: float | None = None
    package_height_mm: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "calibration": self.calibration.to_dict(),
            "pdp_area_cm2": self.pdp_area_cm2,
            "package_width_mm": self.package_width_mm,
            "package_height_mm": self.package_height_mm,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
        }


def calculate_card_ratios(
    corners: np.ndarray,
    card_width_px: float | None = None,
    card_height_px: float | None = None,
    threshold: float = MAX_RATIO_DISCREPANCY_THRESHOLD,
) -> CalibrationMetrics:
    """
    Calculates spatial mm/px resolution with strict dual-edge cross-checking per §4.3 (Step 3).

    Cross-check logic:
    - Long edge: 85.60mm
    - Short edge: 53.98mm
    - Discrepancy: |ratio_long - ratio_short| / min(ratio_long, ratio_short)

    CRITICAL INVARIANT (§4.3 Step 3):
    If long-edge-derived ratio and short-edge-derived ratio disagree by > 5%,
    flag LOW_CONFIDENCE_CALIBRATION rather than silently picking one.
    """
    if card_width_px is None or card_height_px is None:
        ordered = order_quad_corners(corners)
        (tl, tr, br, bl) = ordered
        w_top = float(np.linalg.norm(tr - tl))
        w_bot = float(np.linalg.norm(br - bl))
        h_left = float(np.linalg.norm(bl - tl))
        h_right = float(np.linalg.norm(br - tr))

        measured_w = (w_top + w_bot) / 2.0
        measured_h = (h_left + h_right) / 2.0
    else:
        measured_w = float(card_width_px)
        measured_h = float(card_height_px)

    long_edge_px = max(measured_w, measured_h)
    short_edge_px = min(measured_w, measured_h)

    if long_edge_px <= 0 or short_edge_px <= 0:
        return CalibrationMetrics(
            ratio_short=0.0,
            ratio_long=0.0,
            mm_per_px=None,
            discrepancy_pct=1.0,
            is_consistent=False,
            status=ScanStatus.CALIBRATION_FAILED,
            reason="Reference card dimensions must be strictly positive",
        )

    ratio_long = ISO_CARD_WIDTH_MM / long_edge_px
    ratio_short = ISO_CARD_HEIGHT_MM / short_edge_px

    # Compute relative discrepancy percentage against the conservative baseline
    min_ratio = min(ratio_long, ratio_short)
    discrepancy_pct = abs(ratio_long - ratio_short) / min_ratio if min_ratio > 0 else 1.0

    # Cross-check evaluation
    if discrepancy_pct > threshold:
        reason = (
            f"Dual-edge ratio discrepancy {discrepancy_pct * 100:.2f}% exceeds {threshold * 100:.1f}% limit "
            f"(long-edge {ratio_long:.5f} mm/px vs short-edge {ratio_short:.5f} mm/px) — "
            f"indicates perspective distortion or off-axis tilt"
        )
        logger.warning("Spatial calibration cross-check failed: %s", reason)
        return CalibrationMetrics(
            ratio_short=ratio_short,
            ratio_long=ratio_long,
            mm_per_px=None,
            discrepancy_pct=discrepancy_pct,
            is_consistent=False,
            status=ScanStatus.LOW_CONFIDENCE_CALIBRATION,
            reason=reason,
        )

    # Cross-check verified within 5%: Authoritative ratio is short edge (standard §4.3 Step 3)
    authoritative_mm_per_px = ratio_short
    return CalibrationMetrics(
        ratio_short=ratio_short,
        ratio_long=ratio_long,
        mm_per_px=authoritative_mm_per_px,
        discrepancy_pct=discrepancy_pct,
        is_consistent=True,
        status=ScanStatus.QUEUED,
        reason=None,
    )


def compute_font_height_mm(
    bbox: dict[str, int],
    mm_per_px: float,
) -> float:
    """
    Computes physical font height in millimeters per §4.2 & §4.3 (Step 6).
    font_height_mm = bbox_height_px * mm_per_px
    """
    if mm_per_px <= 0 or not bbox:
        return 0.0

    height_px = max(0, bbox.get("y_max", 0) - bbox.get("y_min", 0))
    return round(height_px * mm_per_px, 2)


def compute_pdp_area_cm2(
    package_bbox: BoundingBox | None,
    mm_per_px: float,
    image_shape: tuple[int, int] | None = None,
) -> float:
    """
    Computes Principal Display Panel (PDP) area in square centimeters per §4.2 & §4.3 (Step 7).
    pdp_area_px2 = area of package_face_bbox (post-dewarp)
    pdp_area_cm2 = pdp_area_px2 * (mm_per_px^2) / 100.0
    """
    if mm_per_px <= 0:
        return 0.0

    if package_bbox is not None and package_bbox.width > 0 and package_bbox.height > 0:
        area_px2 = float(package_bbox.width * package_bbox.height)
    elif image_shape is not None and image_shape[0] > 0 and image_shape[1] > 0:
        area_px2 = float(image_shape[0] * image_shape[1])
    else:
        return 0.0

    area_mm2 = area_px2 * (mm_per_px ** 2)
    area_cm2 = area_mm2 / 100.0  # 1 cm2 = 100 mm2
    return round(area_cm2, 2)


class SpatialCalibrationService:
    """
    Phase 3.3 Orchestrator: Spatial Calibration, Font-to-MM & PDP Area Service.
    """

    def __init__(self, discrepancy_threshold: float = MAX_RATIO_DISCREPANCY_THRESHOLD):
        self.discrepancy_threshold = discrepancy_threshold

    def calibrate_and_measure(
        self,
        preproc_result: PreprocessingResult,
        extraction_result: ExtractionResult,
    ) -> SpatialMeasurementResult:
        """
        Executes spatial calibration and attaches real-world metric measurements
        (font_height_mm and pdp_area_cm2) to extracted declarations.
        """
        # 1. Calibration Failure Check
        if not preproc_result.is_calibration_successful or preproc_result.reference_card_bbox is None:
            calib = CalibrationMetrics(
                ratio_short=0.0,
                ratio_long=0.0,
                mm_per_px=None,
                discrepancy_pct=1.0,
                is_consistent=False,
                status=ScanStatus.CALIBRATION_FAILED,
                reason=preproc_result.failure_reason or "Reference card not detected with required confidence",
            )
            return SpatialMeasurementResult(
                calibration=calib,
                pdp_area_cm2=None,
                fields=extraction_result.fields,
            )

        # 2. Dual-Edge Ratio Cross-Check
        card_bbox = preproc_result.reference_card_bbox
        corners = card_bbox.corners
        if corners is None or len(corners) != 4:
            corners = np.array(
                [
                    [card_bbox.x_min, card_bbox.y_min],
                    [card_bbox.x_max, card_bbox.y_min],
                    [card_bbox.x_max, card_bbox.y_max],
                    [card_bbox.x_min, card_bbox.y_max],
                ],
                dtype=np.float32,
            )

        calib = calculate_card_ratios(
            corners,
            threshold=self.discrepancy_threshold,
        )

        # If cross-check failed (>5%), do NOT estimate font heights or PDP area with unvalidated scale
        if not calib.is_consistent or calib.mm_per_px is None:
            return SpatialMeasurementResult(
                calibration=calib,
                pdp_area_cm2=None,
                fields=extraction_result.fields,
            )

        mm_per_px = calib.mm_per_px

        # 3. PDP Area Computation (§4.3 Step 7)
        pkg_bbox = preproc_result.package_face_bbox
        dewarped_shape = preproc_result.dewarped_package_image.shape[:2] if preproc_result.dewarped_package_image is not None else None
        pdp_area_cm2 = compute_pdp_area_cm2(pkg_bbox, mm_per_px, dewarped_shape)

        pkg_w_mm = round(pkg_bbox.width * mm_per_px, 2) if pkg_bbox else (
            round(dewarped_shape[1] * mm_per_px, 2) if dewarped_shape else None
        )
        pkg_h_mm = round(pkg_bbox.height * mm_per_px, 2) if pkg_bbox else (
            round(dewarped_shape[0] * mm_per_px, 2) if dewarped_shape else None
        )

        # 4. Font Height Computation (§4.3 Step 6) for all extracted fields
        updated_fields: dict[str, ExtractedFieldResult] = {}
        for field_name, res in extraction_result.fields.items():
            font_h_mm = compute_font_height_mm(res.bbox, mm_per_px)
            updated_fields[field_name] = ExtractedFieldResult(
                field_name=res.field_name,
                raw_text=res.raw_text,
                bbox=res.bbox,
                ocr_confidence=res.ocr_confidence,
                semantic_confidence=res.semantic_confidence,
                font_height_mm=font_h_mm,
            )

        return SpatialMeasurementResult(
            calibration=calib,
            pdp_area_cm2=pdp_area_cm2,
            fields=updated_fields,
            package_width_mm=pkg_w_mm,
            package_height_mm=pkg_h_mm,
        )
