from __future__ import annotations

import cv2
import numpy as np


def apply_clahe_contrast(
    image: np.ndarray,
    clip_limit: float = 2.0,
    tile_grid_size: tuple[int, int] = (8, 8),
) -> np.ndarray:
    """
    Contrast Limited Adaptive Histogram Equalization (CLAHE) per §4.3 (Step 2)
    to reduce specular glare, foil reflections, and dynamic range spikes on retail packaging.

    Operates in the perceptually uniform CIE L*a*b* color space on the L* (luminance)
    channel only, preserving chromaticity while normalizing local illumination.

    Args:
        image: Source image as BGR or Grayscale np.ndarray.
        clip_limit: Contrast clipping limit (typically 2.0 - 3.0) to prevent noise amplification.
        tile_grid_size: Grid size for local histogram equalization (default 8x8 blocks).

    Returns:
        Enhanced image with suppressed glare and boosted text stroke contrast.
    """
    if image is None or image.size == 0:
        return image

    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)

    if len(image.shape) == 2:
        # Grayscale image
        return clahe.apply(image)

    if len(image.shape) == 3 and image.shape[2] == 3:
        # Convert BGR -> CIE L*a*b*
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        # Apply CLAHE exclusively to luminance
        enhanced_l = clahe.apply(l_channel)

        # Merge back and convert L*a*b* -> BGR
        merged_lab = cv2.merge([enhanced_l, a_channel, b_channel])
        enhanced_bgr = cv2.cvtColor(merged_lab, cv2.COLOR_LAB2BGR)
        return enhanced_bgr

    return image


def detect_glare_ratio(
    image: np.ndarray,
    luminance_threshold: int = 245,
) -> float:
    """
    Computes the proportion of pixels suffering from specular highlight saturation.

    Args:
        image: BGR or grayscale image.
        luminance_threshold: Grayscale intensity threshold (0-255) considered saturated glare.

    Returns:
        float fraction of saturated pixels in [0.0, 1.0].
    """
    if image is None or image.size == 0:
        return 0.0

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    total_pixels = gray.shape[0] * gray.shape[1]
    if total_pixels == 0:
        return 0.0

    glare_pixels = np.count_nonzero(gray >= luminance_threshold)
    return float(glare_pixels / total_pixels)
