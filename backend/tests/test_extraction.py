from __future__ import annotations

import numpy as np
import pytest

from app.services.vision.detector import GeometricCVDetector
from app.services.vision.extraction_pipeline import (
    get_extraction_pipeline,
)
from app.services.vision.ocr.base import OCRTextLine
from app.services.vision.ocr.deterministic_ocr import DeterministicOCREngine
from app.services.vision.ocr.paddle_ocr import detect_language
from app.services.vision.preprocessor import PreprocessingPipeline
from app.services.vision.semantic.base import (
    MANDATED_SCHEMA_FIELDS,
)
from app.services.vision.semantic.florence2_mapper import Florence2SemanticMapper
from app.services.vision.semantic.rule_based_mapper import (
    UNIT_NORMALIZATION,
    RuleBasedSemanticMapper,
)


class TestOCRLayer:
    """Tests for Phase 3.2 Layer 1 (OCR Subsystem)."""

    def test_ocr_text_line_attributes(self):
        line = OCRTextLine(
            text="Net Qty: 500g",
            bbox={"x_min": 10, "y_min": 20, "x_max": 150, "y_max": 45},
            confidence=0.954,
            lang="en",
        )
        assert line.text == "Net Qty: 500g"
        assert line.confidence == 0.954
        assert line.lang == "en"
        assert len(line.polygon) == 4
        assert line.polygon[0] == [10, 20]
        assert line.polygon[2] == [150, 45]

        d = line.to_dict()
        assert d["text"] == "Net Qty: 500g"
        assert d["confidence"] == 0.954

    def test_language_detection_devanagari(self):
        # English detection
        assert detect_language("Net Quantity 500g") == "en"
        assert detect_language("MRP Rs. 99.00") == "en"

        # Hindi (Devanagari) detection
        assert detect_language("शुद्ध मात्रा 500 ग्राम") == "hi"
        assert detect_language("अधिकतम खुदरा मूल्य ₹149") == "hi"

    def test_deterministic_ocr_engine(self):
        engine = DeterministicOCREngine()
        dummy_img = np.zeros((400, 400, 3), dtype=np.uint8)

        lines = engine.extract_text(dummy_img)
        assert len(lines) >= 8

        texts = [l.text for l in lines]
        assert any("Net Quantity" in t for t in texts)
        assert any("MRP" in t for t in texts)
        assert any("Bengaluru" in t for t in texts)
        assert any("5600" in t for t in texts)
        assert all(0.0 <= l.confidence <= 1.0 for l in lines)


class TestSemanticLayer:
    """Tests for Phase 3.2 Layer 2 (Semantic Mapping & Field Extraction)."""

    @pytest.fixture
    def mock_ocr_lines(self) -> list[OCRTextLine]:
        return [
            OCRTextLine(
                text="Britannia Industries Limited",
                bbox={"x_min": 50, "y_min": 50, "x_max": 350, "y_max": 80},
                confidence=0.96,
                lang="en",
            ),
            OCRTextLine(
                text="Mfg by: Britannia Industries Ltd, Plot 14, Whitefield Industrial Area, Bengaluru, Karnataka - 560066",
                bbox={"x_min": 50, "y_min": 90, "x_max": 450, "y_max": 140},
                confidence=0.94,
                lang="en",
            ),
            OCRTextLine(
                text="Net Quantity: 400 gms",
                bbox={"x_min": 50, "y_min": 150, "x_max": 250, "y_max": 180},
                confidence=0.98,
                lang="en",
            ),
            OCRTextLine(
                text="MRP Rs. 45.00 (Inclusive of all taxes)",
                bbox={"x_min": 50, "y_min": 190, "x_max": 380, "y_max": 220},
                confidence=0.95,
                lang="en",
            ),
            OCRTextLine(
                text="Mfg Date: 15/08/2026",
                bbox={"x_min": 50, "y_min": 230, "x_max": 220, "y_max": 260},
                confidence=0.93,
                lang="en",
            ),
            OCRTextLine(
                text="Consumer Care: feedback@britannia.co.in / Toll Free 1800-425-4444",
                bbox={"x_min": 50, "y_min": 270, "x_max": 480, "y_max": 300},
                confidence=0.91,
                lang="en",
            ),
        ]

    def test_all_mandated_schema_fields_extracted(self, mock_ocr_lines):
        """Verifies all 8 mandated Legal Metrology schema fields are extracted."""
        mapper = RuleBasedSemanticMapper()
        extracted = mapper.map_fields(mock_ocr_lines)

        for field in MANDATED_SCHEMA_FIELDS:
            assert field in extracted, f"Missing mandated schema field: '{field}'"

        assert extracted["net_quantity"].raw_text == "Net Quantity: 400 gms"
        assert extracted["unit"].raw_text == "g"  # Normalized from 'gms'
        assert "45.00" in extracted["mrp"].raw_text
        assert "15/08/2026" in extracted["mfg_date"].raw_text
        assert "Britannia" in extracted["manufacturer_name"].raw_text
        assert "560066" in extracted["pincode"].raw_text
        assert extracted["pincode"].raw_text == "560066"
        assert "1800-425-4444" in extracted["consumer_care"].raw_text
        assert "Whitefield" in extracted["manufacturer_address"].raw_text

    def test_strict_confidence_separation_never_merged(self, mock_ocr_lines):
        """
        CRITICAL INVARIANT TEST:
        ocr_confidence and semantic_confidence MUST be stored separately per field.
        They must NEVER be blended, averaged, or collapsed into one score.
        """
        mapper = RuleBasedSemanticMapper()
        extracted = mapper.map_fields(mock_ocr_lines)

        for field_name, result in extracted.items():
            assert isinstance(result.ocr_confidence, float)
            assert isinstance(result.semantic_confidence, float)
            assert 0.0 <= result.ocr_confidence <= 1.0
            assert 0.0 <= result.semantic_confidence <= 1.0

            # Verify dictionary representation preserves both distinct keys
            d = result.to_dict()
            assert "ocr_confidence" in d
            assert "semantic_confidence" in d
            assert "confidence" not in d  # Must NOT use an ambiguous blended key

            # Check that OCR confidence matches the source OCR line
            if field_name == "net_quantity":
                assert result.ocr_confidence == 0.98
                assert result.semantic_confidence == 0.96

    def test_hindi_declaration_extraction(self):
        """Verifies Hindi/Devanagari declaration parsing."""
        hindi_lines = [
            OCRTextLine(
                text="शुद्ध मात्रा: 500 ग्राम",
                bbox={"x_min": 20, "y_min": 20, "x_max": 200, "y_max": 50},
                confidence=0.92,
                lang="hi",
            ),
            OCRTextLine(
                text="अधिकतम खुदरा मूल्य: ₹120 (सभी कर सहित)",
                bbox={"x_min": 20, "y_min": 60, "x_max": 280, "y_max": 90},
                confidence=0.91,
                lang="hi",
            ),
        ]

        mapper = RuleBasedSemanticMapper()
        extracted = mapper.map_fields(hindi_lines)

        assert "net_quantity" in extracted
        assert "unit" in extracted
        assert extracted["unit"].raw_text == "g"  # 'ग्राम' normalized to standard SI 'g'
        assert extracted["net_quantity"].ocr_confidence == 0.92

    def test_unit_normalization(self):
        """Verifies metric unit normalization against Legal Metrology whitelist."""
        assert UNIT_NORMALIZATION["gms"] == "g"
        assert UNIT_NORMALIZATION["gm"] == "g"
        assert UNIT_NORMALIZATION["grams"] == "g"
        assert UNIT_NORMALIZATION["ग्राम"] == "g"
        assert UNIT_NORMALIZATION["kilograms"] == "kg"
        assert UNIT_NORMALIZATION["किग्रा"] == "kg"
        assert UNIT_NORMALIZATION["ml"] == "ml"
        assert UNIT_NORMALIZATION["millilitre"] == "ml"
        assert UNIT_NORMALIZATION["litres"] == "l"
        assert UNIT_NORMALIZATION["सेमी"] == "cm"

    def test_pincode_isolation_from_address(self):
        """Verifies 6-digit Indian PIN code is isolated without destroying full address."""
        lines = [
            OCRTextLine(
                text="Factory at Plot 88, Okhla Phase III, New Delhi 110020",
                bbox={"x_min": 10, "y_min": 10, "x_max": 400, "y_max": 50},
                confidence=0.95,
                lang="en",
            )
        ]
        mapper = RuleBasedSemanticMapper()
        extracted = mapper.map_fields(lines)

        assert extracted["pincode"].raw_text == "110020"
        assert extracted["pincode"].ocr_confidence == 0.95
        assert "Okhla Phase III" in extracted["manufacturer_address"].raw_text

    def test_florence2_fallback_to_rules(self, mock_ocr_lines):
        """
        Verifies Florence2SemanticMapper automatically falls back to RuleBasedSemanticMapper
        when weights or GPU are not present in test/CI environments.
        """
        # Point to an uninitialized / dummy model ID to test graceful fallback
        mapper = Florence2SemanticMapper(model_id="non-existent/dummy-checkpoint", timeout_sec=0.1)
        extracted = mapper.map_fields(mock_ocr_lines)

        assert "net_quantity" in extracted
        assert "mrp" in extracted
        assert extracted["net_quantity"].ocr_confidence == 0.98
        assert extracted["net_quantity"].semantic_confidence >= 0.85


class TestMasterExtractionPipeline:
    """Tests for Phase 3.2 Master Pipeline (ExtractionPipeline & Factory)."""

    def test_pipeline_execution_with_deterministic_engine(self):
        pipeline = get_extraction_pipeline(ocr_engine="deterministic", semantic_engine="rules")
        dummy_face = np.zeros((600, 400, 3), dtype=np.uint8)

        result = pipeline.process(dummy_face)

        assert result.ocr_engine_name == "DeterministicOCREngine"
        assert result.semantic_engine_name == "RuleBasedSemanticMapper"
        assert len(result.ocr_lines) >= 8
        assert len(result.fields) >= 8  # 8 mandated declarations + indicative product_name

        # All 8 mandated fields present
        for field in MANDATED_SCHEMA_FIELDS:
            assert field in result.fields

        # Serialized dict format verification
        res_dict = result.to_dict()
        assert "fields" in res_dict
        assert "ocr_lines" in res_dict
        assert "metadata" in res_dict
        assert res_dict["metadata"]["total_latency_ms"] >= 0.0

    def test_pipeline_rejects_empty_image(self):
        pipeline = get_extraction_pipeline(ocr_engine="deterministic", semantic_engine="rules")
        with pytest.raises(ValueError, match="package_face image cannot be empty"):
            pipeline.process(np.zeros((0, 0, 3), dtype=np.uint8))

    def test_end_to_end_preprocessing_to_extraction(self):
        """
        E2E Integration:
        Raw frame -> Phase 3.1 PreprocessingPipeline -> package_face -> Phase 3.2 ExtractionPipeline.
        """
        # 1. Synthesize frame with reference card & package face
        frame = np.full((720, 1280, 3), 40, dtype=np.uint8)
        # Draw reference card (blue) at top-left
        frame[50:200, 50:290] = (255, 100, 50)
        # Draw package face (red) at center
        frame[100:600, 400:1000] = (50, 50, 220)

        # 2. Phase 3.1 Preprocessing
        preprocessor = PreprocessingPipeline(detector=GeometricCVDetector())
        preproc_result = preprocessor.process(frame)

        assert preproc_result.is_calibration_successful
        assert preproc_result.dewarped_package_image is not None

        # 3. Phase 3.2 Extraction over post-dewarp package face
        extractor = get_extraction_pipeline(ocr_engine="deterministic", semantic_engine="rules")
        extraction_result = extractor.process(preproc_result.dewarped_package_image)

        assert len(extraction_result.fields) >= 8
        assert "pincode" in extraction_result.fields
        assert extraction_result.fields["unit"].raw_text == "g"

        # Check invariant on e2e output
        for field in extraction_result.fields.values():
            assert field.ocr_confidence > 0.0
            assert field.semantic_confidence > 0.0
