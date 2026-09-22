from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import cv2
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


def measure_glyph_height_px(image: np.ndarray | None, bbox: dict[str, int], min_row_ink: float = 0.02) -> int | None:
    """Measure the height of the numerals/capitals inside an OCR line box (source pixels).

    Schedule II regulates the height of the *numerals*, not the OCR line box
    (which includes padding and detector slack).  The crop is binarised and
    split into connected components (glyphs).  Dots, punctuation and noise are
    discarded; the reported height is the 70th percentile of the remaining
    glyph heights, which in Latin type coincides with cap height — the height
    of digits and capitals — while x-height-only letters sit below it and
    ascender/descender letters sit at or just above it.
    Returns ``None`` when the crop is unusable so the caller can fall back.
    """
    if image is None or image.size == 0 or not bbox:
        return None
    h, w = image.shape[:2]
    x1 = max(0, int(bbox.get("x_min", 0)))
    y1 = max(0, int(bbox.get("y_min", 0)))
    x2 = min(w, int(bbox.get("x_max", 0)))
    y2 = min(h, int(bbox.get("y_max", 0)))
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    crop = image[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    # Text may be dark-on-light or light-on-dark; make ink the minority colour.
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if np.count_nonzero(binary) > binary.size / 2:
        binary = cv2.bitwise_not(binary)
    if binary.mean() / 255.0 < min_row_ink:
        return None

    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count <= 1:
        return None
    heights = stats[1:, cv2.CC_STAT_HEIGHT].astype(float)
    widths = stats[1:, cv2.CC_STAT_WIDTH].astype(float)
    areas = stats[1:, cv2.CC_STAT_AREA].astype(float)
    crop_h = float(y2 - y1)
    tallest = float(heights.max())
    keep = (heights >= 0.35 * tallest) & (areas >= 4) & (heights < crop_h) & (widths < 0.6 * (x2 - x1))
    glyphs = heights[keep]
    if glyphs.size == 0:
        return None
    height = round(float(np.percentile(glyphs, 70)))
    if height < 2:
        return None
    return height


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
        source_image: np.ndarray | None = None,
        measurement_origin: tuple[int, int] = (0, 0),
    ) -> SpatialMeasurementResult:
        """``source_image`` is the image the field boxes refer to, shifted by
        ``measurement_origin`` (boxes are in original-image coordinates; when the
        measurement image is a crop, the crop's top-left is the origin)."""
        self._measurement_origin = measurement_origin
        """
        Executes spatial calibration and attaches real-world metric measurements
        (font_height_mm and pdp_area_cm2) to extracted declarations.
        """
        # 0. Manual calibration (e-commerce listings): the officer declared the
        #    physical package size, so mm/px is known and no card is expected.
        if preproc_result.manual_mm_per_px is not None and preproc_result.reference_card_bbox is None:
            calib = CalibrationMetrics(
                ratio_short=preproc_result.manual_mm_per_px,
                ratio_long=preproc_result.manual_mm_per_px,
                mm_per_px=preproc_result.manual_mm_per_px,
                discrepancy_pct=0.0,
                is_consistent=True,
                status=ScanStatus.QUEUED,
                reason="Manual dimension calibration (declared package size)",
            )
            return self._measure(preproc_result, extraction_result, calib, source_image)

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

        return self._measure(preproc_result, extraction_result, calib, source_image)

    def _measure(
        self,
        preproc_result: PreprocessingResult,
        extraction_result: ExtractionResult,
        calib: CalibrationMetrics,
        source_image: np.ndarray | None,
    ) -> SpatialMeasurementResult:
        mm_per_px = calib.mm_per_px or 0.0

        # 3. PDP Area Computation (§4.3 Step 7)
        pkg_bbox = preproc_result.package_face_bbox
        dewarped_shape = (
            preproc_result.dewarped_package_image.shape[:2]
            if preproc_result.dewarped_package_image is not None
            else None
        )
        if preproc_result.manual_pdp_area_cm2 is not None:
            pdp_area_cm2 = preproc_result.manual_pdp_area_cm2
        else:
            pdp_area_cm2 = compute_pdp_area_cm2(pkg_bbox, mm_per_px, dewarped_shape)

        pkg_w_mm = round(pkg_bbox.width * mm_per_px, 2) if pkg_bbox else (
            round(dewarped_shape[1] * mm_per_px, 2) if dewarped_shape else None
        )
        pkg_h_mm = round(pkg_bbox.height * mm_per_px, 2) if pkg_bbox else (
            round(dewarped_shape[0] * mm_per_px, 2) if dewarped_shape else None
        )

        # 4. Font Height Computation (§4.3 Step 6).  For the fields whose
        #    numeral height is regulated we measure the ink extent; other fields
        #    keep the line-box height as an indicative figure.
        measured_fields = {"net_quantity", "mrp", "unit"}
        updated_fields: dict[str, ExtractedFieldResult] = {}
        for field_name, res in extraction_result.fields.items():
            glyph_px = None
            if field_name in measured_fields:
                ox, oy = getattr(self, "_measurement_origin", (0, 0))
                local_bbox = {
                    "x_min": res.bbox.get("x_min", 0) - ox,
                    "y_min": res.bbox.get("y_min", 0) - oy,
                    "x_max": res.bbox.get("x_max", 0) - ox,
                    "y_max": res.bbox.get("y_max", 0) - oy,
                }
                glyph_px = measure_glyph_height_px(source_image, local_bbox)
            if glyph_px is not None and mm_per_px > 0:
                font_h_mm = round(glyph_px * mm_per_px, 2)
            else:
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
