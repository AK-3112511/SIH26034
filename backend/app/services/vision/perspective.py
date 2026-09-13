from __future__ import annotations

import cv2
import numpy as np

# ISO/IEC 7810 ID-1 standard dimensions (PAN card, debit/credit card, driving license)
ISO_CARD_WIDTH_MM: float = 85.60
ISO_CARD_HEIGHT_MM: float = 53.98
ISO_CARD_ASPECT_RATIO: float = ISO_CARD_WIDTH_MM / ISO_CARD_HEIGHT_MM  # ~1.585772


def order_quad_corners(pts: np.ndarray) -> np.ndarray:
    """
    Order four 2D corner points in canonical order:
    [top-left, top-right, bottom-right, bottom-left].

    Args:
        pts: Array of shape (4, 2) representing the four quadrilateral vertices.

    Returns:
        np.ndarray of shape (4, 2) ordered float32 coordinates.
    """
    pts = np.asarray(pts, dtype=np.float32).reshape((4, 2))
    rect = np.zeros((4, 2), dtype=np.float32)

    # Top-left point has the smallest sum (x + y)
    # Bottom-right point has the largest sum (x + y)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    # Top-right point has the smallest difference (y - x) -> largest (x - y)
    # Bottom-left point has the largest difference (y - x) -> smallest (x - y)
    diff = np.diff(pts, axis=1)  # (y - x)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect


def correct_card_perspective(
    image: np.ndarray,
    corners: np.ndarray,
    target_width: int | None = None,
    target_height: int | None = None,
) -> tuple[np.ndarray, np.ndarray, tuple[int, int]]:
    """
    Applies perspective transformation to rectify an oriented reference card
    into a canonical frontal plane image matching ISO/IEC 7810 ID-1 dimensions.

    Args:
        image: Source image (BGR or grayscale np.ndarray).
        corners: Four corner vertices of the detected reference card.
        target_width: Optional explicit target width in pixels.
        target_height: Optional explicit target height in pixels.

    Returns:
        Tuple containing:
        - warped_card: Rectified card image.
        - H: 3x3 perspective homography matrix.
        - (width, height): Destination pixel dimensions.
    """
    ordered_corners = order_quad_corners(corners)
    (tl, tr, br, bl) = ordered_corners

    # Compute Euclidean distance of top and bottom widths
    width_top = np.linalg.norm(tr - tl)
    width_bottom = np.linalg.norm(br - bl)
    max_width = max(round(width_top), round(width_bottom))

    # Compute Euclidean distance of left and right heights
    height_left = np.linalg.norm(bl - tl)
    height_right = np.linalg.norm(br - tr)
    max_height = max(round(height_left), round(height_right))

    # Ensure valid dimensions
    if max_width < 10:
        max_width = 100
    if max_height < 10:
        max_height = round(max_width / ISO_CARD_ASPECT_RATIO)

    # If oriented vertically, normalize so width is the long edge (85.60 mm)
    if max_height > max_width:
        # Swap or preserve target dimensions
        dst_w = target_width or max_width
        dst_h = target_height or round(dst_w / ISO_CARD_ASPECT_RATIO)
    else:
        dst_w = target_width or max_width
        dst_h = target_height or round(dst_w / ISO_CARD_ASPECT_RATIO)

    # Destination canonical rectangle
    dst_corners = np.array(
        [
            [0, 0],
            [dst_w - 1, 0],
            [dst_w - 1, dst_h - 1],
            [0, dst_h - 1],
        ],
        dtype=np.float32,
    )

    # Compute homography transformation matrix
    H = cv2.getPerspectiveTransform(ordered_corners, dst_corners)
    warped_card = cv2.warpPerspective(image, H, (dst_w, dst_h), flags=cv2.INTER_LINEAR)

    return warped_card, H, (dst_w, dst_h)


def calculate_spatial_ratio(
    corners: np.ndarray,
    card_width_px: float | None = None,
    card_height_px: float | None = None,
) -> tuple[float, float, bool]:
    """
    Calculate the mm_per_px ratio from the detected reference card corners
    per §4.3 (Step 3).

    Cross-checks long-edge (85.60mm) and short-edge (53.98mm) derived ratios.
    If they disagree by > 5%, flags low confidence.

    Args:
        corners: Four ordered corners of the card.
        card_width_px: Optional pre-measured rectified width in pixels.
        card_height_px: Optional pre-measured rectified height in pixels.

    Returns:
        Tuple containing:
        - mm_per_px: Authoritative scale factor (mm per pixel).
        - discrepancy_pct: Percentage difference between long and short edge ratios.
        - is_consistent: True if discrepancy <= 5% (0.05).
    """
    if card_width_px is None or card_height_px is None:
        ordered = order_quad_corners(corners)
        (tl, tr, br, bl) = ordered
        w_top = float(np.linalg.norm(tr - tl))
        w_bot = float(np.linalg.norm(br - bl))
        h_left = float(np.linalg.norm(bl - tl))
        h_right = float(np.linalg.norm(br - tr))

        measured_w = (w_top + w_bot) / 2.0
        measured_h = (h_left + h_right) / 2.0
    else:
        measured_w = float(card_width_px)
        measured_h = float(card_height_px)

    # Identify long edge vs short edge
    long_edge_px = max(measured_w, measured_h)
    short_edge_px = min(measured_w, measured_h)

    if long_edge_px <= 0 or short_edge_px <= 0:
        return 0.0, 1.0, False

    ratio_long = ISO_CARD_WIDTH_MM / long_edge_px
    ratio_short = ISO_CARD_HEIGHT_MM / short_edge_px

    avg_ratio = (ratio_long + ratio_short) / 2.0
    discrepancy_pct = abs(ratio_long - ratio_short) / avg_ratio

    is_consistent = discrepancy_pct <= 0.05

    return avg_ratio, discrepancy_pct, is_consistent
