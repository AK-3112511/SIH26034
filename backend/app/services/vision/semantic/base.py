from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from app.services.vision.ocr.base import OCRTextLine

# The 8 mandated Legal Metrology schema fields per blueprint §4.3 (Step 5) & §11
MANDATED_SCHEMA_FIELDS = (
    "net_quantity",
    "mrp",
    "mfg_date",
    "manufacturer_name",
    "manufacturer_address",
    "pincode",
    "consumer_care",
    "unit",
)


@dataclass
class ExtractedFieldResult:
    """
    Extracted declaration field with strictly separated confidence scores.
    Directly maps to the ExtractedField database model (§11).

    CRITICAL INVARIANT (§4.3 Step 5):
    ocr_confidence and semantic_confidence MUST be stored as distinct numbers.
    They must NEVER be averaged, blended, or collapsed into one score.
    """
    field_name: str
    raw_text: str
    bbox: dict[str, int]
    ocr_confidence: float       # OCR certainty [0.0, 1.0] from Layer 1
    semantic_confidence: float  # VLM/NER certainty [0.0, 1.0] from Layer 2
    font_height_mm: float | None = None  # Calculated in Phase 3.3

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "raw_text": self.raw_text,
            "bbox": self.bbox,
            "ocr_confidence": self.ocr_confidence,
            "semantic_confidence": self.semantic_confidence,
            "font_height_mm": self.font_height_mm,
        }


class BaseSemanticMapper(Protocol):
    """Protocol for semantic mapping engines (VLM Florence-2 or Rule-Based NLP)."""

    def map_fields(
        self,
        ocr_lines: list[OCRTextLine],
        image: np.ndarray | None = None,
    ) -> dict[str, ExtractedFieldResult]:
        """
        Maps raw OCR text lines into the 8 mandated PCR 2011 schema fields.
        """
        ...
