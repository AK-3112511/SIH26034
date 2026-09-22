from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.services.vision.ocr.base import BaseOCREngine, OCRTextLine
from app.services.vision.ocr.deterministic_ocr import DeterministicOCREngine
from app.services.vision.ocr.paddle_ocr import NativePaddleOCREngine
from app.services.vision.semantic.base import (
    BaseSemanticMapper,
    ExtractedFieldResult,
)
from app.services.vision.semantic.florence2_mapper import Florence2SemanticMapper
from app.services.vision.semantic.rule_based_mapper import RuleBasedSemanticMapper

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """
    Complete output of Phase 3.2 text and semantic extraction pipeline.
    """
    fields: dict[str, ExtractedFieldResult]
    ocr_lines: list[OCRTextLine]
    ocr_engine_name: str
    semantic_engine_name: str
    ocr_latency_ms: float
    semantic_latency_ms: float
    total_latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "ocr_lines": [line.to_dict() for line in self.ocr_lines],
            "metadata": {
                "ocr_engine": self.ocr_engine_name,
                "semantic_engine": self.semantic_engine_name,
                "ocr_latency_ms": round(self.ocr_latency_ms, 2),
                "semantic_latency_ms": round(self.semantic_latency_ms, 2),
                "total_latency_ms": round(self.total_latency_ms, 2),
            },
        }


class ExtractionPipeline:
    """
    Phase 3.2 Master Pipeline: OCR & Semantic Mapping.
    Runs over the post-dewarp, glare-reduced package_face image from Phase 3.1.

    Architecture (§4.3 Step 4 & Step 5):
    Layer 1 (OCR): PaddleOCR (English + Hindi) -> produces OCRTextLine list.
    Layer 2 (Semantic): Florence-2 VLM / Rule-Based Mapper -> maps text into 8 mandated PCR 2011 fields.

    CRITICAL INVARIANTS:
    1. Mandatory Schema Fields:
       net_quantity, mrp, mfg_date, manufacturer_name, manufacturer_address,
       pincode, consumer_care, unit.
    2. Confidence Separation:
       ocr_confidence and semantic_confidence MUST be stored separately in every ExtractedFieldResult.
       They are never merged or averaged into a blended score.
    """

    def __init__(
        self,
        ocr_engine: BaseOCREngine,
        semantic_mapper: BaseSemanticMapper,
    ) -> None:
        self.ocr_engine = ocr_engine
        self.semantic_mapper = semantic_mapper

    def process(self, package_face: np.ndarray, origin: tuple[int, int] = (0, 0)) -> ExtractionResult:
        """
        Executes Layer 1 OCR and Layer 2 Semantic Mapping on package_face image.

        ``origin`` is the (x, y) offset of ``package_face`` inside the original
        evidence image.  All returned boxes are translated by it so that they can
        be drawn on the untouched original (chain of custody: the overlay is
        rendered client-side, never burned into pixels).
        """
        if package_face is None or package_face.size == 0:
            raise ValueError("package_face image cannot be empty or None")

        start_total = time.perf_counter()

        # --- Layer 1: OCR ---
        start_ocr = time.perf_counter()
        ocr_lines = self.ocr_engine.extract_text(package_face)
        ocr_time_ms = (time.perf_counter() - start_ocr) * 1000.0
        ox, oy = int(origin[0]), int(origin[1])
        if ox or oy:
            for line in ocr_lines:
                line.bbox = {
                    "x_min": line.bbox["x_min"] + ox,
                    "y_min": line.bbox["y_min"] + oy,
                    "x_max": line.bbox["x_max"] + ox,
                    "y_max": line.bbox["y_max"] + oy,
                }
                if line.polygon:
                    line.polygon = [[int(p[0]) + ox, int(p[1]) + oy] for p in line.polygon]

        # --- Layer 2: Semantic Mapping ---
        start_sem = time.perf_counter()
        fields = self.semantic_mapper.map_fields(ocr_lines, package_face)
        sem_time_ms = (time.perf_counter() - start_sem) * 1000.0

        total_time_ms = (time.perf_counter() - start_total) * 1000.0

        # Enforce invariant: check confidence separation
        for field_name, res in fields.items():
            if not hasattr(res, "ocr_confidence") or not hasattr(res, "semantic_confidence"):
                raise ValueError(
                    f"Invariant violation: field '{field_name}' is missing separate ocr_confidence or semantic_confidence"
                )

        return ExtractionResult(
            fields=fields,
            ocr_lines=ocr_lines,
            ocr_engine_name=type(self.ocr_engine).__name__,
            semantic_engine_name=type(self.semantic_mapper).__name__,
            ocr_latency_ms=ocr_time_ms,
            semantic_latency_ms=sem_time_ms,
            total_latency_ms=total_time_ms,
        )


def get_extraction_pipeline(
    ocr_engine: str = "auto",
    semantic_engine: str = "auto",
    device: str | None = None,
) -> ExtractionPipeline:
    """Factory for the OCR + semantic-mapping pipeline.

    Engine choice is explicit and comes from configuration (``OCR_ENGINE`` /
    ``SEMANTIC_ENGINE``) when the caller passes ``"auto"``.  The mock OCR engine
    returns a fixed synthetic label and is never chosen implicitly outside the
    test suite — if PaddleOCR is requested but not installed we fail loudly
    instead of silently producing fake extractions.

    OCR:      'paddle' (real, CPU/GPU) | 'mock' (alias: 'deterministic')
    Semantic: 'rules' (regex/lexical) | 'florence2' (VLM, falls back to rules if unavailable)
    """
    from app.core.config import settings

    ocr_choice = settings.OCR_ENGINE if ocr_engine == "auto" else ocr_engine
    semantic_choice = settings.SEMANTIC_ENGINE if semantic_engine == "auto" else semantic_engine

    selected_ocr: BaseOCREngine
    if ocr_choice == "paddle":
        try:
            import paddleocr  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "OCR_ENGINE=paddle but PaddleOCR is not installed. "
                "Run `pip install -r requirements-ai.txt` or set OCR_ENGINE=mock for UI development."
            ) from exc
        selected_ocr = NativePaddleOCREngine()
    elif ocr_choice in ("mock", "deterministic"):
        selected_ocr = DeterministicOCREngine()
    else:
        raise ValueError(f"Unknown ocr_engine '{ocr_choice}'. Must be 'paddle' or 'mock'.")

    selected_mapper: BaseSemanticMapper
    if semantic_choice in ("florence2", "florence"):
        selected_mapper = Florence2SemanticMapper(device=device)
    elif semantic_choice == "rules":
        selected_mapper = RuleBasedSemanticMapper()
    else:
        raise ValueError(f"Unknown semantic_engine '{semantic_choice}'. Must be 'rules' or 'florence2'.")

    logger.info("Extraction engines: ocr=%s semantic=%s", type(selected_ocr).__name__, type(selected_mapper).__name__)
    return ExtractionPipeline(ocr_engine=selected_ocr, semantic_mapper=selected_mapper)
