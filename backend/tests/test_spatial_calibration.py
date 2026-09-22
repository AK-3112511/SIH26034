from __future__ import annotations

import numpy as np
import pytest

from app.models.enums import ScanStatus
from app.services.vision.detector import BoundingBox, GeometricCVDetector
from app.services.vision.extraction_pipeline import get_extraction_pipeline
from app.services.vision.perspective import ISO_CARD_HEIGHT_MM, ISO_CARD_WIDTH_MM
from app.services.vision.preprocessor import PreprocessingPipeline
from app.services.vision.spatial_calibration import (
    CalibrationMetrics,
    SpatialCalibrationService,
    calculate_card_ratios,
    compute_font_height_mm,
    compute_pdp_area_cm2,
)


class TestDualEdgeRatioCrossCheck:
    """Tests for Phase 3.3 §4.3 (Step 3) dual-edge ratio calculation and discrepancy cross-check."""

    def test_exact_card_ratio_ideal_perspective(self):
        """Card matching ISO/IEC 7810 nominal proportions yields < 0.1% discrepancy and valid mm_per_px."""
        # 856px wide x 540px high (~10 px per mm)
        corners = np.array([[0, 0], [856, 0], [856, 540], [0, 540]], dtype=np.float32)
        metrics: CalibrationMetrics = calculate_card_ratios(corners, card_width_px=856, card_height_px=540)

        assert metrics.is_consistent is True
        assert metrics.status == ScanStatus.QUEUED
        assert metrics.discrepancy_pct < 0.001
        assert metrics.mm_per_px == pytest.approx(0.1, rel=0.01)
        assert metrics.ratio_long == pytest.approx(0.1, rel=0.01)
        assert metrics.ratio_short == pytest.approx(0.1, rel=0.01)
        assert metrics.reason is None

    def test_ratio_discrepancy_under_5_percent_passes(self):
        """Discrepancy of ~2.8% <= 5.0% threshold passes cross-check."""
        # Long edge: 856px -> 0.1 mm/px
        # Short edge: 525px -> 53.98 / 525 = 0.102819 mm/px (discrepancy ~2.8%)
        corners = np.array([[0, 0], [856, 0], [856, 525], [0, 525]], dtype=np.float32)
        metrics = calculate_card_ratios(corners, card_width_px=856, card_height_px=525)

        assert metrics.is_consistent is True
        assert metrics.status == ScanStatus.QUEUED
        assert metrics.discrepancy_pct <= 0.05
        assert metrics.mm_per_px is not None

    def test_ratio_discrepancy_over_5_percent_flags_low_confidence(self):
        """
        CRITICAL INVARIANT TEST (§4.3 Step 3):
        If long-edge-derived ratio and short-edge-derived ratio disagree by > 5%,
        the engine MUST flag LOW_CONFIDENCE_CALIBRATION rather than silently picking one.
        """
        # Long edge: 856px -> 0.1 mm/px
        # Short edge: 490px -> 53.98 / 490 = 0.11016 mm/px (discrepancy ~10.16% > 5%)
        corners = np.array([[0, 0], [856, 0], [856, 490], [0, 490]], dtype=np.float32)
        metrics = calculate_card_ratios(corners, card_width_px=856, card_height_px=490)

        assert metrics.is_consistent is False
        assert metrics.status == ScanStatus.LOW_CONFIDENCE_CALIBRATION
        assert metrics.discrepancy_pct > 0.05
        # Must NOT silently pick an authoritative scale factor
        assert metrics.mm_per_px is None
        assert "exceeds 5.0% limit" in metrics.reason
        assert "0.10000" in metrics.reason
        assert "0.11016" in metrics.reason

    def test_vertical_card_orientation_handled_correctly(self):
        """Card placed vertically (height > width) correctly identifies long vs short edges."""
        # Width: 540px (short), Height: 856px (long)
        corners = np.array([[0, 0], [540, 0], [540, 856], [0, 856]], dtype=np.float32)
        metrics = calculate_card_ratios(corners, card_width_px=540, card_height_px=856)

        assert metrics.is_consistent is True
        assert metrics.status == ScanStatus.QUEUED
        assert metrics.ratio_long == pytest.approx(ISO_CARD_WIDTH_MM / 856, rel=0.01)
        assert metrics.ratio_short == pytest.approx(ISO_CARD_HEIGHT_MM / 540, rel=0.01)

    def test_zero_or_negative_card_dimensions_rejected(self):
        corners = np.array([[0, 0], [0, 0], [0, 0], [0, 0]], dtype=np.float32)
        metrics = calculate_card_ratios(corners, card_width_px=0, card_height_px=0)

        assert metrics.is_consistent is False
        assert metrics.status == ScanStatus.CALIBRATION_FAILED
        assert metrics.mm_per_px is None


class TestFontHeightToMMConversion:
    """Tests for Phase 3.3 §4.2 & §4.3 (Step 6) font height to mm conversion."""

    def test_exact_blueprint_example_30px_at_point_1(self):
        """
        Direct blueprint §4.2 example verification:
        'If it is 30 pixels tall, it multiplies 30 * 0.1 to declare the font is exactly 3.0 mm tall'
        """
        bbox = {"x_min": 100, "y_min": 200, "x_max": 250, "y_max": 230}
        font_mm = compute_font_height_mm(bbox, mm_per_px=0.10)
        assert font_mm == 3.0

    def test_font_height_with_fractional_mm_per_px(self):
        bbox = {"x_min": 40, "y_min": 100, "x_max": 180, "y_max": 118}  # 18px
        font_mm = compute_font_height_mm(bbox, mm_per_px=0.15)
        # 18 * 0.15 = 2.7 mm
        assert font_mm == 2.7

    def test_font_height_invalid_or_zero_scale(self):
        bbox = {"x_min": 10, "y_min": 10, "x_max": 50, "y_max": 30}
        assert compute_font_height_mm(bbox, mm_per_px=0.0) == 0.0
        assert compute_font_height_mm(bbox, mm_per_px=-0.1) == 0.0
        assert compute_font_height_mm({}, mm_per_px=0.1) == 0.0


class TestPDPAreaCalculation:
    """Tests for Phase 3.3 §4.2 & §4.3 (Step 7) PDP area calculation in cm²."""

    def test_pdp_area_medium_package(self):
        """
        Package face of 800px x 1200px = 960,000 px²
        At mm_per_px = 0.1:
        Area in mm² = 960,000 * 0.01 = 9600 mm²
        Area in cm² = 9600 / 100 = 96.00 cm²
        """
        pkg_box = BoundingBox(x_min=0, y_min=0, x_max=800, y_max=1200, confidence=0.95, label="package_face")
        pdp_cm2 = compute_pdp_area_cm2(pkg_box, mm_per_px=0.10)
        assert pdp_cm2 == 96.00

    def test_pdp_area_large_container_schedule_ii_band(self):
        """Large container > 500 cm² (matches Schedule II upper band test)."""
        pkg_box = BoundingBox(x_min=0, y_min=0, x_max=1500, y_max=2000, confidence=0.98, label="package_face")
        pdp_cm2 = compute_pdp_area_cm2(pkg_box, mm_per_px=0.15)
        # 3,000,000 px² * 0.0225 / 100 = 675.00 cm²
        assert pdp_cm2 == 675.00

    def test_pdp_area_small_pouch_sub_50_cm2(self):
        """Small pouch < 50 cm² (matches Schedule II lower band test)."""
        pkg_box = BoundingBox(x_min=0, y_min=0, x_max=400, y_max=500, confidence=0.90, label="package_face")
        pdp_cm2 = compute_pdp_area_cm2(pkg_box, mm_per_px=0.12)
        # 200,000 px² * 0.0144 / 100 = 28.80 cm²
        assert pdp_cm2 == 28.80

    def test_pdp_area_fallback_to_image_shape(self):
        """When package_bbox is None, computes PDP area directly from dewarped image dimensions."""
        pdp_cm2 = compute_pdp_area_cm2(None, mm_per_px=0.10, image_shape=(1000, 600))
        # 600,000 px² * 0.01 / 100 = 60.00 cm²
        assert pdp_cm2 == 60.00


class TestSpatialCalibrationServiceEndToEnd:
    """Integration tests connecting Phase 3.1 Preprocessing, Phase 3.2 OCR, and Phase 3.3 Calibration."""

    def test_end_to_end_spatial_calibration_pipeline(self):
        # 1. Synthesize realistic inspection frame (reference card at top-left, package at center)
        frame = np.full((720, 1280, 3), 40, dtype=np.uint8)
        # Draw reference card: width 240, height 151 (~1.589 ratio, nominal)
        frame[50:201, 50:290] = (255, 100, 50)
        # Draw package face
        frame[100:600, 400:1000] = (50, 50, 220)

        # 2. Phase 3.1 Preprocessing
        preprocessor = PreprocessingPipeline(detector=GeometricCVDetector())
        preproc_result = preprocessor.process(frame)

        assert preproc_result.is_calibration_successful is True
        assert preproc_result.dewarped_package_image is not None

        # 3. Phase 3.2 OCR & Semantic Extraction
        extractor = get_extraction_pipeline(ocr_engine="deterministic", semantic_engine="rules")
        extraction_result = extractor.process(preproc_result.dewarped_package_image)

        assert len(extraction_result.fields) >= 8

        # 4. Phase 3.3 Spatial Calibration & Measurement Service
        service = SpatialCalibrationService()
        measurement = service.calibrate_and_measure(preproc_result, extraction_result)

        # Verify calibration metrics
        assert measurement.calibration.is_consistent is True
        assert measurement.calibration.status == ScanStatus.QUEUED
        assert measurement.calibration.mm_per_px is not None
        assert measurement.calibration.mm_per_px > 0.0

        # Verify PDP Area
        assert measurement.pdp_area_cm2 is not None
        assert measurement.pdp_area_cm2 > 0.0

        # Verify Font Heights in mm attached to extracted declarations
        fields = measurement.fields
        assert "net_quantity" in fields
        assert "mrp" in fields

        net_qty_field = fields["net_quantity"]
        assert net_qty_field.font_height_mm is not None
        assert net_qty_field.font_height_mm > 0.0

        mrp_field = fields["mrp"]
        assert mrp_field.font_height_mm is not None
        assert mrp_field.font_height_mm > 0.0

        # Serialization to dictionary
        m_dict = measurement.to_dict()
        assert "calibration" in m_dict
        assert "pdp_area_cm2" in m_dict
        assert "fields" in m_dict
        assert m_dict["calibration"]["status"] == "QUEUED"

    def test_preprocessor_flags_low_confidence_when_aspect_ratio_skewed(self):
        """
        Verifies that when a card is photographed at an extreme angle (ratio discrepancy > 5%),
        PreprocessingPipeline immediately marks status LOW_CONFIDENCE_CALIBRATION and halts mm estimation.
        """
        frame = np.full((720, 1280, 3), 40, dtype=np.uint8)
        # Distorted card: width 240, height 100 (ratio 2.4 >> 1.586)
        frame[50:150, 50:290] = (255, 100, 50)
        frame[100:600, 400:1000] = (50, 50, 220)

        preprocessor = PreprocessingPipeline(detector=GeometricCVDetector())
        preproc_result = preprocessor.process(frame)

        # Should be caught by detector or calibration cross-check
        assert preproc_result.is_calibration_successful is False
        assert preproc_result.status in (ScanStatus.CALIBRATION_FAILED, ScanStatus.LOW_CONFIDENCE_CALIBRATION)
        assert preproc_result.mm_per_px is None
