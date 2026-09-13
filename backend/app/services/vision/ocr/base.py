from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np


@dataclass
class OCRTextLine:
    """
    Represents a recognized text line or phrase from the OCR engine per §4.3 (Step 4).
    Output format: {text, bbox, confidence, lang, polygon}
    """
    text: str
    bbox: dict[str, int]  # {"x_min": int, "y_min": int, "x_max": int, "y_max": int}
    confidence: float     # Optical character recognition confidence score [0.0, 1.0]
    lang: str = "en"      # Language tag ('en' for English, 'hi' for Hindi)
    polygon: list[list[int]] | None = None  # Original 4-point quadrilateral polygon

    def __post_init__(self) -> None:
        if self.polygon is None and self.bbox:
            x_min = self.bbox.get("x_min", 0)
            y_min = self.bbox.get("y_min", 0)
            x_max = self.bbox.get("x_max", 0)
            y_max = self.bbox.get("y_max", 0)
            self.polygon = [
                [x_min, y_min],
                [x_max, y_min],
                [x_max, y_max],
                [x_min, y_max],
            ]

    @property
    def height_px(self) -> int:
        return max(0, self.bbox.get("y_max", 0) - self.bbox.get("y_min", 0))

    @property
    def width_px(self) -> int:
        return max(0, self.bbox.get("x_max", 0) - self.bbox.get("x_min", 0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "lang": self.lang,
            "polygon": self.polygon,
        }


class BaseOCREngine(Protocol):
    """Protocol for OCR engines."""

    def extract_text(self, image: np.ndarray) -> list[OCRTextLine]:
        """
        Extract text lines with spatial bounding boxes and confidence scores
        from the dewarped package face image.
        """
        ...
