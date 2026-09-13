from __future__ import annotations

import enum
import os
from dataclasses import dataclass, field
from typing import Protocol

import cv2
import numpy as np

from app.services.vision.perspective import ISO_CARD_ASPECT_RATIO, order_quad_corners


class DetectorEngine(str, enum.Enum):
    YOLOV8 = "yolov8"
    CV_GEOM = "cv_geom"
    MOCK = "mock"


@dataclass
class BoundingBox:
    """Bounding box with optional 4-point quadrilateral corner vertices."""
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    confidence: float
    label: str
    corners: np.ndarray | None = None  # Shape (4, 2) if quadrilateral corners available

    @property
    def width(self) -> int:
        return max(0, self.x_max - self.x_min)

    @property
    def height(self) -> int:
        return max(0, self.y_max - self.y_min)

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def aspect_ratio(self) -> float:
        min_dim = min(self.width, self.height)
        if min_dim == 0:
            return 0.0
        return max(self.width, self.height) / min_dim

    def to_crop(self, image: np.ndarray) -> np.ndarray:
        """Extract rectangular crop from image."""
        h, w = image.shape[:2]
        x1 = max(0, min(self.x_min, w))
        y1 = max(0, min(self.y_min, h))
        x2 = max(x1, min(self.x_max, w))
        y2 = max(y1, min(self.y_max, h))
        return image[y1:y2, x1:x2]


@dataclass
class DetectionResult:
    reference_card: BoundingBox | None = None
    package_face: BoundingBox | None = None
    engine: str = DetectorEngine.CV_GEOM.value
    all_detections: list[BoundingBox] = field(default_factory=list)

    @property
    def is_card_detected(self) -> bool:
        return self.reference_card is not None

    @property
    def card_confidence(self) -> float:
        return self.reference_card.confidence if self.reference_card else 0.0


class DetectorProtocol(Protocol):
    def detect(
        self,
        image: np.ndarray,
        reference_object_type: str | None = None,
    ) -> DetectionResult:
        ...


class GeometricCVDetector:
    """
    Deterministic Computer Vision detector using multi-channel gradient boundaries,
    contour hierarchy, and approxPolyDP quadrilateral perspective aspect-ratio scoring.

    Provides an auditable, zero-GPU baseline and production fallback when neural
    YOLOv8 weights are unavailable or offline.
    """

    def __init__(
        self,
        min_card_area_ratio: float = 0.005,
        max_card_area_ratio: float = 0.50,
        aspect_ratio_min: float = 1.15,
        aspect_ratio_max: float = 2.10,
    ):
        self.min_card_area_ratio = min_card_area_ratio
        self.max_card_area_ratio = max_card_area_ratio
        self.aspect_ratio_min = aspect_ratio_min
        self.aspect_ratio_max = aspect_ratio_max

    def detect(
        self,
        image: np.ndarray,
        reference_object_type: str | None = None,
    ) -> DetectionResult:
        if image is None or image.size == 0:
            return DetectionResult(engine=DetectorEngine.CV_GEOM.value)

        h, w = image.shape[:2]
        total_area = float(h * w)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        blurred = cv2.GaussianBlur(gray, (5, 5), 1.5)

        # Multi-scale edge detection for robust contour discovery
        edges = cv2.Canny(blurred, 40, 140)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(edges, kernel, iterations=1)

        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        card_candidates: list[tuple[float, BoundingBox]] = []
        package_candidates: list[BoundingBox] = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < total_area * self.min_card_area_ratio:
                continue

            # Candidate for package face (large dominant central region)
            if area > total_area * 0.15:
                x, y, bw, bh = cv2.boundingRect(cnt)
                package_candidates.append(
                    BoundingBox(
                        x_min=x,
                        y_min=y,
                        x_max=x + bw,
                        y_max=y + bh,
                        confidence=float(min(area / total_area, 0.98)),
                        label="package_face",
                    )
                )

            # Candidate for reference card
            if total_area * self.min_card_area_ratio <= area <= total_area * self.max_card_area_ratio:
                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)

                # Reference card is a convex quadrilateral
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    pts = approx.reshape((4, 2))
                    ordered_pts = order_quad_corners(pts)

                    (tl, tr, br, bl) = ordered_pts
                    top_w = np.linalg.norm(tr - tl)
                    bot_w = np.linalg.norm(br - bl)
                    left_h = np.linalg.norm(bl - tl)
                    right_h = np.linalg.norm(br - tr)

                    cand_w = (top_w + bot_w) / 2.0
                    cand_h = (left_h + right_h) / 2.0

                    if min(cand_w, cand_h) > 0:
                        cand_ratio = max(cand_w, cand_h) / min(cand_w, cand_h)

                        if self.aspect_ratio_min <= cand_ratio <= self.aspect_ratio_max:
                            diff = abs(cand_ratio - ISO_CARD_ASPECT_RATIO)
                            # Closeness to nominal 1.58577 ratio yields confidence score
                            card_conf = float(np.clip(1.0 - (diff / 0.40), 0.50, 0.98))

                            bx_min = int(np.min(pts[:, 0]))
                            by_min = int(np.min(pts[:, 1]))
                            bx_max = int(np.max(pts[:, 0]))
                            by_max = int(np.max(pts[:, 1]))

                            card_bbox = BoundingBox(
                                x_min=bx_min,
                                y_min=by_min,
                                x_max=bx_max,
                                y_max=by_max,
                                confidence=card_conf,
                                label="reference_card",
                                corners=ordered_pts,
                            )
                            card_candidates.append((card_conf, card_bbox))

        # Select highest confidence reference card
        best_card: BoundingBox | None = None
        if card_candidates:
            card_candidates.sort(key=lambda x: x[0], reverse=True)
            best_card = card_candidates[0][1]

        # Select best package face candidate (excluding card bounding region)
        best_package: BoundingBox | None = None
        if package_candidates:
            # Sort by area descending
            package_candidates.sort(key=lambda x: x.area, reverse=True)
            for pkg in package_candidates:
                if best_card is not None and pkg.x_min == best_card.x_min and pkg.y_min == best_card.y_min:
                    continue
                best_package = pkg
                break

        # Fallback package face if none segmented cleanly: entire image excluding card
        if best_package is None:
            if best_card is not None and best_card.x_max < w:
                # Package is to the right or left of card
                best_package = BoundingBox(
                    x_min=0,
                    y_min=0,
                    x_max=w,
                    y_max=h,
                    confidence=0.88,
                    label="package_face",
                )
            else:
                best_package = BoundingBox(
                    x_min=0,
                    y_min=0,
                    x_max=w,
                    y_max=h,
                    confidence=0.85,
                    label="package_face",
                )

        detections = []
        if best_card:
            detections.append(best_card)
        if best_package:
            detections.append(best_package)

        return DetectionResult(
            reference_card=best_card,
            package_face=best_package,
            engine=DetectorEngine.CV_GEOM.value,
            all_detections=detections,
        )


class CustomYOLOv8Detector:
    """
    YOLOv8 detector wrapper for custom-trained Legal Metrology model weights.

    Detects classes:
      - 0: reference_card
      - 1: package_face

    If custom weights file does not exist at runtime, gracefully routes to
    GeometricCVDetector with an auditable fallback flag.
    """

    def __init__(
        self,
        weights_path: str | None = None,
        fallback_detector: DetectorProtocol | None = None,
        confidence_threshold: float = 0.25,
    ):
        self.weights_path = weights_path
        self.confidence_threshold = confidence_threshold
        self.fallback = fallback_detector or GeometricCVDetector()
        self._model = None
        self._is_yolo_loaded = False

        if weights_path and os.path.exists(weights_path):
            try:
                from ultralytics import YOLO
                self._model = YOLO(weights_path)
                self._is_yolo_loaded = True
            except Exception:
                self._is_yolo_loaded = False

    def detect(
        self,
        image: np.ndarray,
        reference_object_type: str | None = None,
    ) -> DetectionResult:
        if not self._is_yolo_loaded or self._model is None:
            # Fallback to Geometric CV engine when custom weights are absent
            res = self.fallback.detect(image, reference_object_type)
            res.engine = f"{DetectorEngine.CV_GEOM.value} (yolov8 weights absent fallback)"
            return res

        results = self._model(image, conf=self.confidence_threshold, verbose=False)

        best_card: BoundingBox | None = None
        best_package: BoundingBox | None = None
        all_boxes: list[BoundingBox] = []

        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                xyxy = box.xyxy[0].cpu().numpy().astype(int)

                if cls_id == 0:  # reference_card
                    # Synthesize corners from oriented box or bounding rect
                    bx1, by1, bx2, by2 = xyxy
                    corners = np.array(
                        [[bx1, by1], [bx2, by1], [bx2, by2], [bx1, by2]],
                        dtype=np.float32,
                    )
                    bbox = BoundingBox(
                        x_min=bx1,
                        y_min=by1,
                        x_max=bx2,
                        y_max=by2,
                        confidence=conf,
                        label="reference_card",
                        corners=corners,
                    )
                    all_boxes.append(bbox)
                    if best_card is None or conf > best_card.confidence:
                        best_card = bbox

                elif cls_id == 1:  # package_face
                    bx1, by1, bx2, by2 = xyxy
                    bbox = BoundingBox(
                        x_min=bx1,
                        y_min=by1,
                        x_max=bx2,
                        y_max=by2,
                        confidence=conf,
                        label="package_face",
                    )
                    all_boxes.append(bbox)
                    if best_package is None or conf > best_package.confidence:
                        best_package = bbox

        return DetectionResult(
            reference_card=best_card,
            package_face=best_package,
            engine=DetectorEngine.YOLOV8.value,
            all_detections=all_boxes,
        )


def get_detector(
    engine: str = "auto",
    model_path: str | None = None,
) -> DetectorProtocol:
    """
    Factory resolving the appropriate detector implementation.

    Args:
        engine: 'auto', 'yolov8', or 'cv_geom'.
        model_path: Optional path to custom trained YOLOv8 weights.
    """
    clean_engine = engine.lower().strip()

    if clean_engine == DetectorEngine.CV_GEOM.value:
        return GeometricCVDetector()

    # If explicit path not provided, check default location
    resolved_path = model_path
    if not resolved_path:
        default_candidate = os.path.join(
            os.path.dirname(__file__), "weights", "metrology_yolov8.pt"
        )
        if os.path.exists(default_candidate):
            resolved_path = default_candidate

    if clean_engine in (DetectorEngine.YOLOV8.value, "auto"):
        if resolved_path and os.path.exists(resolved_path):
            return CustomYOLOv8Detector(weights_path=resolved_path)
        if clean_engine == "auto":
            # Auto-selection defaults to deterministic Geometric CV when weights are absent
            return GeometricCVDetector()
        return CustomYOLOv8Detector(weights_path=resolved_path)

    return GeometricCVDetector()
