from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.models.enums import ScanStatus
from app.services.vision.detector import (
    BoundingBox,
    DetectionResult,
    DetectorProtocol,
    get_detector,
)
from app.services.vision.dewarp import (
    analyze_curvature,
    cylindrical_dewarp,
)
from app.services.vision.glare_reduction import (
    apply_clahe_contrast,
)
from app.services.vision.perspective import (
    correct_card_perspective,
)
from app.services.vision.spatial_calibration import calculate_card_ratios


@dataclass
class PreprocessingResult:
    """Encapsulates outputs and intermediate representations of Phase 3.1 preprocessing."""

    status: ScanStatus
    is_calibration_successful: bool
    failure_reason: str | None = None
    detection_result: DetectionResult | None = None
    package_face_bbox: BoundingBox | None = None
    reference_card_bbox: BoundingBox | None = None
    dewarped_package_image: np.ndarray | None = None
    warped_card_image: np.ndarray | None = None
    mm_per_px: float | None = None
    ratio_discrepancy_pct: float | None = None
    is_ratio_consistent: bool = False
    is_cylindrical: bool = False
    curvature_score: float = 0.0
    clahe_applied: bool = False


class PreprocessingPipeline:
    """
    Master Preprocessing Stage implementing MetrologyAI Elevated Blueprint §4.3 (Steps 1–2).

    1. Detection Pass:
       - Runs detector to locate package_face_bbox and reference_card_bbox.
       - If reference_card_bbox missing or confidence < 0.85:
           Marks status CALIBRATION_FAILED and immediately halts pipeline.
           DO NOT estimate mm from assumptions.
    2. OpenCV Preprocessing (only executed if calibration succeeded):
       - Perspective correction on card corners via cv2.getPerspectiveTransform.
       - Curvature analysis & cylindrical dewarp if container is a bottle/can.
       - CLAHE contrast pass to suppress specular glare and foil reflections.
    """

    def __init__(
        self,
        detector: DetectorProtocol | None = None,
        card_confidence_threshold: float = 0.85,
    ):
        self.detector = detector or get_detector()
        self.card_confidence_threshold = card_confidence_threshold

    def process(
        self,
        image: np.ndarray,
        reference_object_type: str | None = None,
    ) -> PreprocessingResult:
        """
        Execute the complete preprocessing pipeline on a raw image.

        Args:
            image: Source image (BGR np.ndarray).
            reference_object_type: Optional container type hint ('box', 'bottle', 'manual').

        Returns:
            PreprocessingResult with status, dewarped image, and spatial calibration data.
        """
        if image is None or image.size == 0:
            return PreprocessingResult(
                status=ScanStatus.CALIBRATION_FAILED,
                is_calibration_successful=False,
                failure_reason="Invalid or empty image supplied",
            )

        # -------------------------------------------------------------
        # Step 1: Detection pass and calibration gating (§4.3 Step 1)
        # -------------------------------------------------------------
        det_result = self.detector.detect(image, reference_object_type)
        card_bbox = det_result.reference_card
        package_bbox = det_result.package_face

        # Strict Calibration Gate: card must be present and confidence >= 0.85
        if card_bbox is None or card_bbox.confidence < self.card_confidence_threshold:
            conf_str = f"{card_bbox.confidence:.2f}" if card_bbox else "None"
            return PreprocessingResult(
                status=ScanStatus.CALIBRATION_FAILED,
                is_calibration_successful=False,
                failure_reason=(
                    f"Reference card missing or confidence {conf_str} "
                    f"< mandatory threshold {self.card_confidence_threshold:.2f}"
                ),
                detection_result=det_result,
                package_face_bbox=package_bbox,
                reference_card_bbox=card_bbox,
                # Explicitly do NOT compute mm_per_px or estimate measurements
                mm_per_px=None,
            )

        # -------------------------------------------------------------
        # Step 2: OpenCV preprocessing (§4.3 Step 2)
        # Only reached if reference card calibration succeeded (conf >= 0.85)
        # -------------------------------------------------------------

        # 2a. Perspective correction on reference card corners
        corners = card_bbox.corners
        if corners is None or len(corners) != 4:
            # Fallback corners from bounding box rectangle if corners not explicitly supplied
            corners = np.array(
                [
                    [card_bbox.x_min, card_bbox.y_min],
                    [card_bbox.x_max, card_bbox.y_min],
                    [card_bbox.x_max, card_bbox.y_max],
                    [card_bbox.x_min, card_bbox.y_max],
                ],
                dtype=np.float32,
            )

        warped_card, _, (_card_w_px, _card_h_px) = correct_card_perspective(
            image, corners
        )

        # Compute mm_per_px spatial resolution ratio and verify dual-edge cross-check (§4.3 Step 3)
        calib_metrics = calculate_card_ratios(corners=corners)

        if not calib_metrics.is_consistent:
            return PreprocessingResult(
                status=ScanStatus.LOW_CONFIDENCE_CALIBRATION,
                is_calibration_successful=False,
                failure_reason=calib_metrics.reason,
                detection_result=det_result,
                package_face_bbox=package_bbox,
                reference_card_bbox=card_bbox,
                warped_card_image=warped_card,
                mm_per_px=None,
                ratio_discrepancy_pct=calib_metrics.discrepancy_pct,
                is_ratio_consistent=False,
            )

        mm_per_px = calib_metrics.mm_per_px
        discrepancy = calib_metrics.discrepancy_pct
        is_consistent = calib_metrics.is_consistent

        # 2b. Extract package face crop
        if package_bbox is not None:
            package_crop = package_bbox.to_crop(image)
        else:
            package_crop = image.copy()

        # 2c. Curvature heuristic and cylindrical dewarp
        is_cylindrical, curvature_score = analyze_curvature(
            package_crop, reference_object_type=reference_object_type
        )

        if is_cylindrical:
            dewarped_package = cylindrical_dewarp(package_crop)
        else:
            dewarped_package = package_crop

        # 2d. CLAHE contrast pass to suppress glare and foil reflection
        enhanced_package = apply_clahe_contrast(
            dewarped_package,
            clip_limit=2.0,
            tile_grid_size=(8, 8),
        )

        return PreprocessingResult(
            status=ScanStatus.QUEUED,
            is_calibration_successful=True,
            detection_result=det_result,
            package_face_bbox=package_bbox,
            reference_card_bbox=card_bbox,
            dewarped_package_image=enhanced_package,
            warped_card_image=warped_card,
            mm_per_px=mm_per_px,
            ratio_discrepancy_pct=discrepancy,
            is_ratio_consistent=is_consistent,
            is_cylindrical=is_cylindrical,
            curvature_score=curvature_score,
            clahe_applied=True,
        )
