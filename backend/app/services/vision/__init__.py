"""MetrologyAI Vision and Preprocessing Subsystem (§4.3)"""

from app.services.vision.detector import (
    BoundingBox,
    CustomYOLOv8Detector,
    DetectionResult,
    DetectorEngine,
    DetectorProtocol,
    GeometricCVDetector,
    get_detector,
)
from app.services.vision.dewarp import (
    analyze_curvature,
    cylindrical_dewarp,
)
from app.services.vision.extraction_pipeline import (
    ExtractionPipeline,
    ExtractionResult,
    get_extraction_pipeline,
)
from app.services.vision.glare_reduction import (
    apply_clahe_contrast,
)
from app.services.vision.ocr import (
    BaseOCREngine,
    DeterministicOCREngine,
    NativePaddleOCREngine,
    OCRTextLine,
    detect_language,
)
from app.services.vision.perspective import (
    ISO_CARD_ASPECT_RATIO,
    ISO_CARD_HEIGHT_MM,
    ISO_CARD_WIDTH_MM,
    calculate_spatial_ratio,
    correct_card_perspective,
    order_quad_corners,
)
from app.services.vision.preprocessor import (
    PreprocessingPipeline,
    PreprocessingResult,
)
from app.services.vision.semantic import (
    MANDATED_SCHEMA_FIELDS,
    BaseSemanticMapper,
    ExtractedFieldResult,
    Florence2SemanticMapper,
    RuleBasedSemanticMapper,
)
from app.services.vision.spatial_calibration import (
    MAX_RATIO_DISCREPANCY_THRESHOLD,
    CalibrationMetrics,
    SpatialCalibrationService,
    SpatialMeasurementResult,
    calculate_card_ratios,
    compute_font_height_mm,
    compute_pdp_area_cm2,
)

__all__ = [
    # Detection & Preprocessing (Phase 3.1)
    "BoundingBox",
    "DetectionResult",
    "DetectorEngine",
    "DetectorProtocol",
    "GeometricCVDetector",
    "CustomYOLOv8Detector",
    "get_detector",
    "correct_card_perspective",
    "calculate_spatial_ratio",
    "order_quad_corners",
    "ISO_CARD_WIDTH_MM",
    "ISO_CARD_HEIGHT_MM",
    "ISO_CARD_ASPECT_RATIO",
    "analyze_curvature",
    "cylindrical_dewarp",
    "apply_clahe_contrast",
    "PreprocessingPipeline",
    "PreprocessingResult",
    # OCR (Phase 3.2 Layer 1)
    "OCRTextLine",
    "BaseOCREngine",
    "NativePaddleOCREngine",
    "DeterministicOCREngine",
    "detect_language",
    # Semantic Mapping (Phase 3.2 Layer 2)
    "ExtractedFieldResult",
    "BaseSemanticMapper",
    "MANDATED_SCHEMA_FIELDS",
    "RuleBasedSemanticMapper",
    "Florence2SemanticMapper",
    # Master Extraction Pipeline (Phase 3.2)
    "ExtractionPipeline",
    "ExtractionResult",
    "get_extraction_pipeline",
    # Spatial Calibration (Phase 3.3)
    "MAX_RATIO_DISCREPANCY_THRESHOLD",
    "CalibrationMetrics",
    "SpatialMeasurementResult",
    "SpatialCalibrationService",
    "calculate_card_ratios",
    "compute_font_height_mm",
    "compute_pdp_area_cm2",
]
