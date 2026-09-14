"""OCR Subsystem: PaddleOCR and Deterministic Test Engine."""

from app.services.vision.ocr.base import BaseOCREngine, OCRTextLine
from app.services.vision.ocr.deterministic_ocr import DeterministicOCREngine
from app.services.vision.ocr.paddle_ocr import NativePaddleOCREngine, detect_language

__all__ = [
    "BaseOCREngine",
    "DeterministicOCREngine",
    "NativePaddleOCREngine",
    "OCRTextLine",
    "detect_language",
]
