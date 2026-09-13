from __future__ import annotations

import numpy as np

from app.services.vision.ocr.base import OCRTextLine
from app.services.vision.ocr.paddle_ocr import detect_language


class DeterministicOCREngine:
    """
    Engine 1B: Deterministic / Test OCR Engine.
    Provides sub-millisecond, zero-GPU deterministic execution for test suites,
    CI validation, and air-gapped deployments where external neural models are absent.
    """

    def __init__(
        self,
        default_lines: list[OCRTextLine] | None = None,
        confidence: float | None = None,
    ):
        self._fixture_lines: list[OCRTextLine] | None = default_lines
        self.confidence = confidence

    def set_fixture_lines(self, lines: list[OCRTextLine]) -> None:
        """Inject predetermined OCR text lines for deterministic test verification."""
        self._fixture_lines = lines

    def extract_text(self, image: np.ndarray) -> list[OCRTextLine]:
        # 1. Return pre-injected test lines if set
        if self._fixture_lines is not None:
            return list(self._fixture_lines)

        if image is None or image.size == 0:
            return []

        h, w = image.shape[:2]

        # 2. Standard synthetic retail packaging declaration template
        # Generates realistic bounding boxes spanning the package face
        sample_declarations = [
            ("BRITANNIA INDUSTRIES LIMITED", 0.98, 30, 60),
            ("Mfg by: Plot 12, Industrial Suburb, Peenya, Bengaluru, Karnataka 560058", 0.96, 75, 110),
            ("Net Quantity: 500 g", 0.99, 125, 155),
            ("MRP Rs. 120.00 (inclusive of all taxes)", 0.97, 170, 200),
            ("PKD: 12/2025", 0.95, 215, 240),
            ("Consumer Care: 1800-425-4444 / feedback@britannia.co.in", 0.97, 255, 285),
            ("शुद्ध मात्रा: 500 ग्राम", 0.96, 300, 330),  # Hindi net quantity line
            ("Plot 14, Whitefield Industrial Area, Bengaluru - 560066", 0.95, 345, 375),  # Address with PIN
        ]

        lines: list[OCRTextLine] = []
        for text, conf, y1_rel, y2_rel in sample_declarations:
            y1 = int((y1_rel / 400.0) * h)
            y2 = int((y2_rel / 400.0) * h)
            x1 = int(w * 0.08)
            x2 = int(w * 0.92)

            effective_conf = self.confidence if self.confidence is not None else conf
            lines.append(
                OCRTextLine(
                    text=text,
                    bbox={"x_min": x1, "y_min": y1, "x_max": x2, "y_max": y2},
                    confidence=effective_conf,
                    lang=detect_language(text),
                )
            )

        return lines
