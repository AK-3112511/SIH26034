from __future__ import annotations

import logging
import re

import numpy as np

from app.services.vision.ocr.base import OCRTextLine

logger = logging.getLogger(__name__)

# Devanagari Unicode Block (U+0900 - U+097F) for Hindi detection
DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]")


def detect_language(text: str) -> str:
    """Classifies text line as Hindi ('hi') if Devanagari characters are present, else English ('en')."""
    if DEVANAGARI_REGEX.search(text):
        return "hi"
    return "en"


class NativePaddleOCREngine:
    """
    Production Engine 1A: Native PaddleOCR (PP-OCRv4).
    Processes post-dewarp package face images to extract bounding boxes,
    text content, and confidence scores across English and Hindi.
    """

    def __init__(
        self,
        lang: str = "hi",
        use_angle_cls: bool = True,
        use_gpu: bool = False,
    ):
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self.use_gpu = use_gpu
        self._ocr = None
        self._initialized = False

        self._init_engine()

    def _init_engine(self) -> None:
        try:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                use_angle_cls=self.use_angle_cls,
                lang=self.lang,
                use_gpu=self.use_gpu,
                show_log=False,
            )
            self._initialized = True
            logger.info("PaddleOCR engine initialized successfully with lang=%s", self.lang)
        except Exception as e:
            self._initialized = False
            self._ocr = None
            logger.warning("PaddleOCR initialization unavailable: %s", e)

    @property
    def is_available(self) -> bool:
        return self._initialized and self._ocr is not None

    def extract_text(self, image: np.ndarray) -> list[OCRTextLine]:
        if not self.is_available or image is None or image.size == 0:
            return []

        try:
            results = self._ocr.ocr(image, cls=self.use_angle_cls)
            lines: list[OCRTextLine] = []

            if not results or not results[0]:
                return lines

            for item in results[0]:
                box_pts, (text, conf) = item
                if not text or not text.strip():
                    continue

                pts = np.array(box_pts, dtype=int)
                x_min = int(np.min(pts[:, 0]))
                y_min = int(np.min(pts[:, 1]))
                x_max = int(np.max(pts[:, 0]))
                y_max = int(np.max(pts[:, 1]))

                polygon = [(int(p[0]), int(p[1])) for p in box_pts]
                lang = detect_language(text)

                lines.append(
                    OCRTextLine(
                        text=text.strip(),
                        bbox={
                            "x_min": x_min,
                            "y_min": y_min,
                            "x_max": x_max,
                            "y_max": y_max,
                        },
                        confidence=float(conf),
                        lang=lang,
                        polygon=polygon,
                    )
                )

            return lines
        except Exception as e:
            logger.error("Error during PaddleOCR inference: %s", e)
            return []
