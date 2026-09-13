import os
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.enums import ScanStatus
from app.services.vision.detector import (
    BoundingBox,
    CustomYOLOv8Detector,
    DetectionResult,
    GeometricCVDetector,
)
from app.services.vision.dewarp import (
    analyze_curvature,
    cylindrical_dewarp,
)
from app.services.vision.glare_reduction import (
    apply_clahe_contrast,
    detect_glare_ratio,
)
from app.services.vision.perspective import (
    ISO_CARD_ASPECT_RATIO,
    calculate_spatial_ratio,
    correct_card_perspective,
    order_quad_corners,
)
from app.services.vision.preprocessor import (
    PreprocessingPipeline,
)


def _create_synthetic_box_with_card(
    width: int = 800,
    height: int = 600,
    card_aspect_ratio: float = 1.5858,
) -> np.ndarray:
    """Creates a static test image with a flat retail box and an ISO/IEC 7810 reference card."""
    img = np.full((height, width, 3), 235, dtype=np.uint8)

    # Draw retail package box (centered-right)
    pkg_x1, pkg_y1 = 280, 80
    pkg_x2, pkg_y2 = 740, 520
    cv2.rectangle(img, (pkg_x1, pkg_y1), (pkg_x2, pkg_y2), (70, 130, 200), -1)
    cv2.rectangle(img, (pkg_x1, pkg_y1), (pkg_x2, pkg_y2), (30, 30, 30), 3)

    # Package label text lines
    for ly in range(pkg_y1 + 50, pkg_y2 - 50, 40):
        cv2.line(img, (pkg_x1 + 30, ly), (pkg_x2 - 40, ly), (255, 255, 255), 3)

    # Draw reference card (left side, nominal ratio 1.5858)
    card_w = 190
    card_h = round(card_w / card_aspect_ratio)
    card_x1, card_y1 = 50, 220
    card_x2, card_y2 = card_x1 + card_w, card_y1 + card_h

    cv2.rectangle(img, (card_x1, card_y1), (card_x2, card_y2), (180, 160, 60), -1)
    cv2.rectangle(img, (card_x1, card_y1), (card_x2, card_y2), (20, 20, 20), 2)
    # Smart chip indicator
    cv2.rectangle(img, (card_x1 + 20, card_y1 + 25), (card_x1 + 50, card_y1 + 50), (220, 210, 120), -1)

    return img


def _create_synthetic_bottle_with_card(
    width: int = 800,
    height: int = 600,
) -> np.ndarray:
    """Creates a static test image of a cylindrical bottle with curved rims and a reference card."""
    img = _create_synthetic_box_with_card(width, height)

    # Overwrite package area with a cylindrical bottle having elliptical rims
    pkg_x1, pkg_y1 = 320, 60
    pkg_x2, pkg_y2 = 680, 540
    cv2.rectangle(img, (pkg_x1 - 10, pkg_y1 - 10), (pkg_x2 + 10, pkg_y2 + 10), (235, 235, 235), -1)

    # Draw bottle body with gradient shading
    center_x = (pkg_x1 + pkg_x2) // 2
    radius_x = (pkg_x2 - pkg_x1) // 2

    # Cylindrical Lambertian shading
    for x in range(pkg_x1, pkg_x2):
        norm_col = (x - center_x) / float(radius_x)
        if abs(norm_col) <= 1.0:
            shade = int(220 * np.cos(norm_col * (np.pi / 2.5)))
            cv2.line(img, (x, pkg_y1 + 20), (x, pkg_y2 - 20), (shade, shade, int(shade * 0.9)), 1)

    # Top and bottom arched rims
    cv2.ellipse(img, (center_x, pkg_y1 + 20), (radius_x, 25), 0, 0, 360, (40, 40, 40), 3)
    cv2.ellipse(img, (center_x, pkg_y2 - 20), (radius_x, 25), 0, 0, 360, (40, 40, 40), 3)

    return img


# ==============================================================================
# 1. Perspective Correction & Spatial Calibration Tests (§4.3 Steps 1–3)
# ==============================================================================

def test_order_quad_corners():
    # Unordered points
    pts = np.array([[100, 200], [10, 15], [110, 20], [5, 195]], dtype=np.float32)
    ordered = order_quad_corners(pts)

    assert ordered.shape == (4, 2)
    # top-left should be (10, 15)
    np.testing.assert_allclose(ordered[0], [10, 15])
    # top-right should be (110, 20)
    np.testing.assert_allclose(ordered[1], [110, 20])
    # bottom-right should be (100, 200)
    np.testing.assert_allclose(ordered[2], [100, 200])
    # bottom-left should be (5, 195)
    np.testing.assert_allclose(ordered[3], [5, 195])


def test_perspective_rectification_recovers_iso_ratio():
    # Generate an image with a rotated/tilted quadrilateral
    canvas = np.zeros((400, 400, 3), dtype=np.uint8)
    src_corners = np.array(
        [[60, 80], [250, 50], [280, 190], [80, 220]], dtype=np.float32
    )
    cv2.fillPoly(canvas, [src_corners.astype(int)], (200, 200, 200))

    warped, _h_mat, (w, h) = correct_card_perspective(canvas, src_corners)

    assert warped is not None
    assert w > 0 and h > 0
    actual_ratio = w / h
    # Expected ratio should match ISO/IEC 7810 nominal 1.5858
    assert abs(actual_ratio - ISO_CARD_ASPECT_RATIO) < 0.05


def test_spatial_ratio_calculation():
    # A card with width 856px and height 540px (~10 px per mm)
    corners = np.array([[0, 0], [856, 0], [856, 540], [0, 540]], dtype=np.float32)
    mm_per_px, discrepancy, is_consistent = calculate_spatial_ratio(corners, 856, 540)

    # 85.60 / 856 = 0.1 mm/px, 53.98 / 540 = 0.09996 mm/px
    assert mm_per_px == pytest.approx(0.1, rel=0.01)
    assert discrepancy < 0.01
    assert is_consistent is True


# ==============================================================================
# 2. Curvature Heuristic & Cylindrical Dewarp Tests (§4.3 Step 2)
# ==============================================================================

def test_analyze_curvature_heuristics():
    # Flat box
    flat_box = np.full((300, 300, 3), 180, dtype=np.uint8)
    cv2.rectangle(flat_box, (10, 10), (290, 290), (40, 40, 40), 2)
    is_cyl, score = analyze_curvature(flat_box, reference_object_type="box")
    assert is_cyl is False
    assert score == 0.0

    # Explicit bottle type hint
    is_cyl, score = analyze_curvature(flat_box, reference_object_type="bottle")
    assert is_cyl is True
    assert score == 1.0


def test_cylindrical_dewarp_remap_geometry():
    # Generate image with vertical stripes
    img = np.full((200, 200, 3), 240, dtype=np.uint8)
    for x in range(10, 190, 20):
        cv2.line(img, (x, 0), (x, 200), (0, 0, 0), 2)

    dewarped = cylindrical_dewarp(img, fov_angle_deg=60.0)

    assert dewarped is not None
    assert dewarped.shape[0] == img.shape[0]
    # Arc length of 60 deg cylinder is strictly larger than projected chord width
    assert dewarped.shape[1] >= img.shape[1]


# ==============================================================================
# 3. CLAHE Contrast & Glare Reduction Tests (§4.3 Step 2)
# ==============================================================================

def test_apply_clahe_contrast_glare_reduction():
    # Create an image with severe glare specular hotspot
    img = np.full((200, 200, 3), 100, dtype=np.uint8)
    # Specular saturated spot
    cv2.circle(img, (100, 100), 30, (255, 255, 255), -1)

    initial_glare = detect_glare_ratio(img, luminance_threshold=245)
    assert initial_glare > 0.05

    enhanced = apply_clahe_contrast(img, clip_limit=2.0, tile_grid_size=(8, 8))

    assert enhanced is not None
    assert enhanced.shape == img.shape
    # CLAHE redistributes high luminance local peaks into local histogram bins
    gray_enhanced = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
    # The absolute peak should be tempered / local contrast broadened
    assert np.mean(gray_enhanced) != np.mean(img)


# ==============================================================================
# 4. Detector Protocol & Dual-Engine Tests
# ==============================================================================

def test_geometric_cv_detector_finds_card_and_package():
    img = _create_synthetic_box_with_card()
    detector = GeometricCVDetector()
    result = detector.detect(img)

    assert result.is_card_detected is True
    assert result.reference_card is not None
    assert result.reference_card.confidence >= 0.85
    assert result.reference_card.corners is not None
    assert len(result.reference_card.corners) == 4
    assert result.package_face is not None


def test_custom_yolov8_detector_falls_back_when_weights_absent():
    # Pass non-existent path to verify fallback
    detector = CustomYOLOv8Detector(weights_path="non_existent_weights.pt")
    img = _create_synthetic_box_with_card()
    result = detector.detect(img)

    assert result.is_card_detected is True
    assert "fallback" in result.engine.lower()


# ==============================================================================
# 5. Full Preprocessing Pipeline End-to-End Tests (§4.3 Steps 1–2)
# ==============================================================================

def test_full_pipeline_valid_flat_box():
    img = _create_synthetic_box_with_card()
    pipeline = PreprocessingPipeline(card_confidence_threshold=0.85)
    result = pipeline.process(img, reference_object_type="box")

    assert result.status == ScanStatus.QUEUED
    assert result.is_calibration_successful is True
    assert result.failure_reason is None
    assert result.mm_per_px is not None
    assert result.mm_per_px > 0.0
    assert result.is_cylindrical is False
    assert result.clahe_applied is True
    assert result.dewarped_package_image is not None
    assert result.warped_card_image is not None


def test_full_pipeline_cylindrical_bottle_triggers_dewarp():
    img = _create_synthetic_bottle_with_card()
    pipeline = PreprocessingPipeline(card_confidence_threshold=0.85)
    result = pipeline.process(img, reference_object_type="bottle")

    assert result.status == ScanStatus.QUEUED
    assert result.is_calibration_successful is True
    assert result.is_cylindrical is True
    assert result.dewarped_package_image is not None


def test_full_pipeline_missing_card_triggers_calibration_failed():
    # Image with ONLY package box, NO reference card
    img = np.full((600, 800, 3), 235, dtype=np.uint8)
    cv2.rectangle(img, (200, 100), (600, 500), (80, 140, 200), -1)
    cv2.rectangle(img, (200, 100), (600, 500), (30, 30, 30), 2)

    pipeline = PreprocessingPipeline(card_confidence_threshold=0.85)
    result = pipeline.process(img)

    # Invariant: Must mark CALIBRATION_FAILED and halt immediately
    assert result.status == ScanStatus.CALIBRATION_FAILED
    assert result.is_calibration_successful is False
    assert result.failure_reason is not None
    assert "Reference card missing" in result.failure_reason
    # Invariant: Must NOT estimate mm_per_px from assumptions
    assert result.mm_per_px is None


def test_full_pipeline_low_confidence_card_triggers_calibration_failed():
    img = _create_synthetic_box_with_card()

    # Create mock detector that detects card but with confidence 0.72 < 0.85
    class LowConfidenceMockDetector:
        def detect(self, image, reference_object_type=None):
            card = BoundingBox(
                x_min=50,
                y_min=200,
                x_max=240,
                y_max=320,
                confidence=0.72,  # Below 0.85 threshold
                label="reference_card",
                corners=np.array([[50, 200], [240, 200], [240, 320], [50, 320]], dtype=np.float32),
            )
            pkg = BoundingBox(
                x_min=280,
                y_min=80,
                x_max=740,
                y_max=520,
                confidence=0.95,
                label="package_face",
            )
            return DetectionResult(reference_card=card, package_face=pkg, engine="mock")

    pipeline = PreprocessingPipeline(
        detector=LowConfidenceMockDetector(),
        card_confidence_threshold=0.85,
    )
    result = pipeline.process(img)

    # Invariant: Must mark CALIBRATION_FAILED when confidence < 0.85
    assert result.status == ScanStatus.CALIBRATION_FAILED
    assert result.is_calibration_successful is False
    assert "0.72" in result.failure_reason
    # Invariant: Must NOT estimate measurements
    assert result.mm_per_px is None
