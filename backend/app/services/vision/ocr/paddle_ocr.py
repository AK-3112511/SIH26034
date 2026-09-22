"""PaddleOCR (PP-OCRv4) engine — the production text reader.

Indian labels mix Latin and Devanagari script, and PaddleOCR ships one
recognition model per script.  The engine therefore runs two passes:

* ``en`` — primary; reads every Latin line (numbers, units, MRP, addresses).
* ``devanagari`` — secondary; only its lines that actually contain
  Devanagari characters are kept, and only where they do not overlap a
  higher-confidence Latin line.

Model objects are expensive to build (~1–2 s, plus a one-time download of the
weights), so they are created lazily and cached per process.  Paddle's
inference is not thread-safe, so a lock serialises calls — background
processing already caps concurrency, this is the last line of defence.
"""
from __future__ import annotations

import logging
import re
import threading
from typing import Any

import cv2
import numpy as np

from app.services.vision.ocr.base import OCRTextLine

logger = logging.getLogger(__name__)

# Devanagari Unicode Block (U+0900 - U+097F) for Hindi detection
DEVANAGARI_REGEX = re.compile(r"[ऀ-ॿ]")

# Longest image side passed to the recogniser.  Larger inputs cost CPU time
# without improving character accuracy; boxes are scaled back to source pixels.
MAX_OCR_SIDE_PX = 1600
MIN_LINE_CONFIDENCE = 0.30
MIN_DEVANAGARI_CONFIDENCE = 0.50


def detect_language(text: str) -> str:
    """Classifies text line as Hindi ('hi') if Devanagari characters are present, else English ('en')."""
    if DEVANAGARI_REGEX.search(text):
        return "hi"
    return "en"


def _overlap_fraction(candidate: dict[str, int], other: dict[str, int]) -> float:
    """Fraction of ``candidate``'s area covered by ``other``."""
    ix = max(0, min(candidate["x_max"], other["x_max"]) - max(candidate["x_min"], other["x_min"]))
    iy = max(0, min(candidate["y_max"], other["y_max"]) - max(candidate["y_min"], other["y_min"]))
    area = max(1, (candidate["x_max"] - candidate["x_min"]) * (candidate["y_max"] - candidate["y_min"]))
    return (ix * iy) / float(area)


def _box_iou(a: dict[str, int], b: dict[str, int]) -> float:
    ix = max(0, min(a["x_max"], b["x_max"]) - max(a["x_min"], b["x_min"]))
    iy = max(0, min(a["y_max"], b["y_max"]) - max(a["y_min"], b["y_min"]))
    inter = ix * iy
    if inter == 0:
        return 0.0
    area_a = (a["x_max"] - a["x_min"]) * (a["y_max"] - a["y_min"])
    area_b = (b["x_max"] - b["x_min"]) * (b["y_max"] - b["y_min"])
    return inter / float(area_a + area_b - inter)


_MODEL_CACHE: dict[str, Any] = {}
_MODEL_LOCK = threading.Lock()
_INFER_LOCK = threading.Lock()


def _load_model(lang: str, use_angle_cls: bool, use_gpu: bool):
    """Build (or fetch the cached) PaddleOCR model for one language."""
    key = f"{lang}:{int(use_angle_cls)}:{int(use_gpu)}"
    with _MODEL_LOCK:
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]
        from paddleocr import PaddleOCR

        model = PaddleOCR(use_angle_cls=use_angle_cls, lang=lang, use_gpu=use_gpu, show_log=False)
        _MODEL_CACHE[key] = model
        logger.info("PaddleOCR model loaded: lang=%s gpu=%s", lang, use_gpu)
        return model


class NativePaddleOCREngine:
    """Production OCR engine: PaddleOCR PP-OCRv4, English + Devanagari."""

    def __init__(
        self,
        languages: tuple[str, ...] = ("en", "devanagari"),
        use_angle_cls: bool = True,
        use_gpu: bool = False,
        lazy: bool = True,
    ):
        self.languages = languages
        self.use_angle_cls = use_angle_cls
        self.use_gpu = use_gpu
        self._models: dict[str, Any] = {}
        self._init_error: str | None = None
        if not lazy:
            self.warm_up()

    # ------------------------------------------------------------------ setup
    def warm_up(self) -> bool:
        """Load every configured model now (called from application startup)."""
        for lang in self.languages:
            if lang in self._models:
                continue
            try:
                self._models[lang] = _load_model(lang, self.use_angle_cls, self.use_gpu)
            except Exception as exc:  # pragma: no cover - depends on local install
                self._init_error = f"{lang}: {exc}"
                logger.error("PaddleOCR model '%s' failed to load: %s", lang, exc)
                if lang == self.languages[0]:
                    return False
        return self.languages[0] in self._models

    @property
    def is_available(self) -> bool:
        if self.languages[0] in self._models:
            return True
        return self.warm_up()

    # -------------------------------------------------------------- inference
    def extract_text(self, image: np.ndarray) -> list[OCRTextLine]:
        if image is None or image.size == 0 or not self.is_available:
            return []

        work, scale = self._prepare(image)
        primary_lang = self.languages[0]
        lines = self._run(primary_lang, work, scale, keep_devanagari_only=False)

        for lang in self.languages[1:]:
            if lang not in self._models:
                continue
            for cand in self._run(lang, work, scale, keep_devanagari_only=True):
                # Each model "reads" the other script as look-alike glyphs, so
                # where a Hindi candidate overlaps a Latin line the more
                # confident reading wins (the Latin model is primary on ties).
                clashes = [ln for ln in lines if _overlap_fraction(cand.bbox, ln.bbox) > 0.25]
                if not clashes:
                    lines.append(cand)
                    continue
                best_clash = max(clashes, key=lambda ln: ln.confidence)
                if cand.confidence > best_clash.confidence + 0.05:
                    for ln in clashes:
                        lines.remove(ln)
                    lines.append(cand)

        lines.sort(key=lambda ln: (ln.bbox["y_min"], ln.bbox["x_min"]))
        return lines

    def _prepare(self, image: np.ndarray) -> tuple[np.ndarray, float]:
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        h, w = image.shape[:2]
        longest = max(h, w)
        if longest <= MAX_OCR_SIDE_PX:
            return image, 1.0
        scale = MAX_OCR_SIDE_PX / float(longest)
        resized = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        return resized, scale

    def _run(self, lang: str, image: np.ndarray, scale: float, keep_devanagari_only: bool) -> list[OCRTextLine]:
        model = self._models.get(lang)
        if model is None:
            return []
        try:
            with _INFER_LOCK:
                results = model.ocr(image, cls=self.use_angle_cls)
        except Exception as exc:
            logger.error("PaddleOCR inference failed (lang=%s): %s", lang, exc)
            return []

        lines: list[OCRTextLine] = []
        if not results or not results[0]:
            return lines

        inv = 1.0 / scale
        for item in results[0]:
            try:
                box_pts, (text, conf) = item
            except (TypeError, ValueError):
                continue
            text = (text or "").strip()
            if not text:
                continue
            conf = float(conf)
            has_devanagari = bool(DEVANAGARI_REGEX.search(text))
            if keep_devanagari_only:
                letters = re.findall(r"[^\W\d_]", text)
                devanagari_share = len(DEVANAGARI_REGEX.findall(text)) / max(1, len(letters))
                if not has_devanagari or conf < MIN_DEVANAGARI_CONFIDENCE or devanagari_share < 0.5:
                    continue
            if conf < MIN_LINE_CONFIDENCE:
                continue

            pts = np.array(box_pts, dtype=np.float32) * inv
            polygon = [(round(float(p[0])), round(float(p[1]))) for p in pts]
            lines.append(
                OCRTextLine(
                    text=text,
                    bbox={
                        "x_min": int(np.floor(pts[:, 0].min())),
                        "y_min": int(np.floor(pts[:, 1].min())),
                        "x_max": int(np.ceil(pts[:, 0].max())),
                        "y_max": int(np.ceil(pts[:, 1].max())),
                    },
                    confidence=conf,
                    lang="hi" if has_devanagari else "en",
                    polygon=polygon,
                )
            )
        return lines


_SHARED_ENGINE: NativePaddleOCREngine | None = None


def get_shared_paddle_engine() -> NativePaddleOCREngine:
    """Process-wide engine instance (models are cached at module level anyway)."""
    global _SHARED_ENGINE
    if _SHARED_ENGINE is None:
        _SHARED_ENGINE = NativePaddleOCREngine()
    return _SHARED_ENGINE
