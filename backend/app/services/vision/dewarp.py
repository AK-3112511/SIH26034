from __future__ import annotations

import math

import cv2
import numpy as np


def analyze_curvature(
    image: np.ndarray,
    reference_object_type: str | None = None,
    curvature_threshold: float = 0.25,
) -> tuple[bool, float]:
    """
    Curvature heuristic per §4.3 (Step 2) to evaluate whether a package face
    represents a cylindrical surface (bottle, tin can, aerosol can) vs a planar surface (box, carton).

    Args:
        image: Package face image crop (BGR or Grayscale).
        reference_object_type: Optional explicit container classification ('box', 'bottle', 'manual').
        curvature_threshold: Normalized score threshold above which cylinder is declared.

    Returns:
        Tuple containing:
        - is_cylindrical: bool indicating whether cylindrical dewarping should be applied.
        - curvature_score: float metric in [0.0, 1.0] representing curvature strength.
    """
    # 1. Check explicit packaging type metadata if supplied
    if reference_object_type is not None:
        clean_type = reference_object_type.lower().strip()
        if clean_type in ("bottle", "can", "cylinder", "cylindrical"):
            return True, 1.0
        if clean_type in ("box", "carton", "flat"):
            return False, 0.0

    if image is None or image.size == 0:
        return False, 0.0

    h, w = image.shape[:2]
    if h < 20 or w < 20:
        return False, 0.0

    # 2. Image-based heuristic: Top & bottom boundary curve fitting
    # Cylinders viewed with any pitch angle exhibit elliptical arc contours at top/bottom rims.
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Analyze top band (0% to 20% of height) and bottom band (80% to 100% of height)
    band_h = max(int(h * 0.2), 5)
    top_band = blurred[:band_h, :]
    bot_band = blurred[-band_h:, :]

    def _measure_band_sagitta(band: np.ndarray) -> float:
        # Detect prominent edges along columns
        sobel_y = cv2.Sobel(band, cv2.CV_64F, 0, 1, ksize=3)
        edge_pts_x = []
        edge_pts_y = []

        step_x = max(w // 25, 1)
        for x in range(0, w, step_x):
            col_grad = np.abs(sobel_y[:, x])
            if np.max(col_grad) > 30.0:
                y_peak = np.argmax(col_grad)
                edge_pts_x.append(x)
                edge_pts_y.append(y_peak)

        if len(edge_pts_x) < 8:
            return 0.0

        xs = np.array(edge_pts_x, dtype=np.float64)
        ys = np.array(edge_pts_y, dtype=np.float64)

        # Fit 2nd-degree polynomial y = a*x^2 + b*x + c
        try:
            poly = np.polyfit(xs, ys, 2)
            a = poly[0]
            # Sagitta (height of the arc) = |a| * (W/2)^2
            sagitta = abs(a) * ((w / 2.0) ** 2)
            # Normalized by band height
            return float(min(sagitta / band_h, 1.0))
        except Exception:
            return 0.0

    top_sagitta = _measure_band_sagitta(top_band)
    bot_sagitta = _measure_band_sagitta(bot_band)
    contour_curve_score = max(top_sagitta, bot_sagitta)

    # 3. Horizontal shading profile: Cylinders show symmetrical horizontal luminance fall-off
    mid_strip = gray[int(h * 0.35) : int(h * 0.65), :]
    horizontal_profile = np.mean(mid_strip, axis=0)
    # Fit quadratic to horizontal profile to detect parabolic Lambertian shading
    norm_x = np.linspace(-1, 1, w)
    try:
        shading_poly = np.polyfit(norm_x, horizontal_profile, 2)
        shading_curvature = -shading_poly[0] / (np.max(horizontal_profile) + 1e-5)
        shading_score = float(np.clip(shading_curvature, 0.0, 1.0))
    except Exception:
        shading_score = 0.0

    # Combined curvature metric
    combined_score = float(np.clip(0.7 * contour_curve_score + 0.3 * shading_score, 0.0, 1.0))
    is_cylindrical = combined_score >= curvature_threshold

    return is_cylindrical, combined_score


def cylindrical_dewarp(
    image: np.ndarray,
    fov_angle_deg: float = 60.0,
    aspect_ratio_correction: bool = True,
) -> np.ndarray:
    """
    Cylindrical surface dewarping per §4.3 (Step 2).
    Inverts the orthographic/perspective lateral compression of labels wrapped
    around cylindrical surfaces (bottles, tin cans), stretching compressed margins
    back into a flattened planar projection suitable for OCR and PDP area math.

    Mapping Formulation:
    For a cylinder of radius R centered at x0 = W/2:
        x_proj = x0 + R * sin(theta)
        where theta = (x_dest - x0) / R
    Inverse lookup for cv2.remap:
        x_src = x0 + R * sin((x_dest - x0) / R)
        y_src = y_dest

    Args:
        image: Package face image crop to dewarp (H x W).
        fov_angle_deg: Visible angular span of the cylinder in degrees (typically 45-80 deg).
        aspect_ratio_correction: Whether to scale output width to match unrolled arc length.

    Returns:
        Dewarped planar image as np.ndarray.
    """
    if image is None or image.size == 0:
        return image

    h, w = image.shape[:2]
    if h < 10 or w < 10:
        return image

    # Half-angle in radians
    theta_max = math.radians(fov_angle_deg / 2.0)
    # Effective radius R such that R * sin(theta_max) = W / 2
    r = (w / 2.0) / math.sin(theta_max)
    # Arc length of the unrolled cylinder surface
    arc_length = 2.0 * r * theta_max
    out_w = round(arc_length) if aspect_ratio_correction else w

    x0_src = w / 2.0
    x0_dst = out_w / 2.0

    # Create coordinate grid for destination image
    dst_x, dst_y = np.meshgrid(
        np.arange(out_w, dtype=np.float32),
        np.arange(h, dtype=np.float32),
    )

    # Destination angular coordinate theta across unrolled surface
    theta = (dst_x - x0_dst) / r

    # Source coordinate lookup map
    map_x = (x0_src + r * np.sin(theta)).astype(np.float32)
    map_y = dst_y.astype(np.float32)

    # Remap using bicubic interpolation
    dewarped = cv2.remap(
        image,
        map_x,
        map_y,
        interpolation=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )

    return dewarped
