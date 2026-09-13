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

    def process(self, package_face: np.ndarray) -> ExtractionResult:
        """
        Executes Layer 1 OCR and Layer 2 Semantic Mapping on package_face image.
        """
        if package_face is None or package_face.size == 0:
            raise ValueError("package_face image cannot be empty or None")

        start_total = time.perf_counter()

        # --- Layer 1: OCR ---
        start_ocr = time.perf_counter()
        ocr_lines = self.ocr_engine.extract_text(package_face)
        ocr_time_ms = (time.perf_counter() - start_ocr) * 1000.0

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
    """
    Factory function for ExtractionPipeline adhering to production/fallback decision trees.

    OCR Selection:
    - 'paddle': NativePaddleOCREngine
    - 'deterministic': DeterministicOCREngine
    - 'auto': NativePaddleOCREngine if paddleocr installed, else DeterministicOCREngine

    Semantic Selection:
    - 'florence': Florence2SemanticMapper
    - 'rules': RuleBasedSemanticMapper
    - 'auto': Florence2SemanticMapper (with dynamic fallback to RuleBasedSemanticMapper)
    """
    # 1. Resolve OCR Engine
    selected_ocr: BaseOCREngine
    if ocr_engine == "paddle":
        selected_ocr = NativePaddleOCREngine()
    elif ocr_engine == "deterministic":
        selected_ocr = DeterministicOCREngine()
    elif ocr_engine == "auto":
        try:
            import paddleocr  # noqa: F401
            selected_ocr = NativePaddleOCREngine()
            logger.info("Auto-selected OCR engine: NativePaddleOCREngine")
        except ImportError:
            selected_ocr = DeterministicOCREngine()
            logger.info("Auto-selected OCR engine: DeterministicOCREngine (paddleocr not installed)")
    else:
        raise ValueError(f"Unknown ocr_engine '{ocr_engine}'. Must be 'paddle', 'deterministic', or 'auto'.")

    # 2. Resolve Semantic Mapper
    selected_mapper: BaseSemanticMapper
    if semantic_engine == "florence":
        selected_mapper = Florence2SemanticMapper(device=device)
    elif semantic_engine == "rules":
        selected_mapper = RuleBasedSemanticMapper()
    elif semantic_engine == "auto":
        # Florence2SemanticMapper automatically falls back to RuleBased if torch/transformers/weights unavailable
        selected_mapper = Florence2SemanticMapper(device=device)
    else:
        raise ValueError(f"Unknown semantic_engine '{semantic_engine}'. Must be 'florence', 'rules', or 'auto'.")

    return ExtractionPipeline(ocr_engine=selected_ocr, semantic_mapper=selected_mapper)
