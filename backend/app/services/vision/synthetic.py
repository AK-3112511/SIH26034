"""Render synthetic evidence photos: a package label next to an ISO/IEC 7810 card.

Used by the demo seeder and the test-suite so that "demo data" is produced by
the *real* pipeline (real OCR, real calibration, real rules) instead of being
typed into the database.  Every geometric quantity is known exactly, which
also makes these images a regression fixture for the calibration maths.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services.vision.perspective import ISO_CARD_HEIGHT_MM, ISO_CARD_WIDTH_MM

_FONT_CANDIDATES = (
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/ARIAL.TTF",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)
_BOLD_CANDIDATES = (
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (_BOLD_CANDIDATES if bold else _FONT_CANDIDATES):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    for path in glob.glob("C:/Windows/Fonts/*.ttf")[:1] + glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)[:1]:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


@dataclass
class SyntheticLabel:
    """Declarations printed on the synthetic package face."""

    brand: str = "SUNRISE FOODS"
    product: str = "Golden Crunch Biscuits"
    net_quantity: str = "Net Quantity: 200 g"
    mrp: str = "MRP Rs. 45.00 (inclusive of all taxes)"
    manufacturer: str = "Mfd by: Sunrise Foods Pvt Ltd"
    address: str = "Plot 12, MIDC Industrial Area, Pune, Maharashtra 411018"
    consumer_care: str = "Consumer care: 1800-123-4567 | care@sunrisefoods.in"
    mfg_date: str = "Pkd: 08/2026"
    extra_lines: list[str] = field(default_factory=list)
    # Physical layout
    mm_per_px: float = 0.12  # 0.12 mm/px ≈ 210 dpi phone capture
    label_width_mm: float = 150.0
    label_height_mm: float = 100.0
    numeral_height_mm: float = 3.0  # cap height of the net-quantity numerals
    body_height_mm: float = 2.2
    brand_height_mm: float = 7.0
    background: tuple[int, int, int] = (250, 246, 236)
    ink: tuple[int, int, int] = (25, 25, 30)


def render_label_with_card(spec: SyntheticLabel, seed: int = 0) -> tuple[np.ndarray, dict]:
    """Return ``(bgr_image, geometry)`` where geometry has the exact card/label boxes."""
    rng = np.random.default_rng(seed)
    def px(mm: float) -> int:
        return round(mm / spec.mm_per_px)


    label_w, label_h = px(spec.label_width_mm), px(spec.label_height_mm)
    card_w, card_h = px(ISO_CARD_WIDTH_MM), px(ISO_CARD_HEIGHT_MM)
    margin = px(12)
    canvas_w = margin * 3 + label_w + card_w
    canvas_h = margin * 2 + max(label_h, card_h)

    # Slightly textured "table" background so contour detection has to work.
    base = np.full((canvas_h, canvas_w, 3), 128, np.uint8) + rng.integers(-12, 12, (canvas_h, canvas_w, 1), dtype=np.int16).astype(np.int8)
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")
    draw = ImageDraw.Draw(img)

    # --- package face
    lx, ly = margin, margin
    draw.rectangle([lx, ly, lx + label_w, ly + label_h], fill=spec.background, outline=(60, 60, 60), width=2)

    # Text: cap-height in PIL ≈ 0.72 × font size for Arial, so size = mm / 0.72.
    def font_for_cap_mm(mm: float, bold: bool = False):
        return _font(max(8, round(px(mm) / 0.72)), bold)

    y = ly + px(6)
    x = lx + px(6)
    draw.text((x, y), spec.brand, font=font_for_cap_mm(spec.brand_height_mm, bold=True), fill=spec.ink)
    y += px(spec.brand_height_mm * 1.9)
    draw.text((x, y), spec.product, font=font_for_cap_mm(spec.body_height_mm * 1.6), fill=spec.ink)
    y += px(spec.body_height_mm * 1.6 * 2.2)

    qty_font = font_for_cap_mm(spec.numeral_height_mm, bold=True)
    draw.text((x, y), spec.net_quantity, font=qty_font, fill=spec.ink)
    y += px(spec.numeral_height_mm * 2.4)

    body = font_for_cap_mm(spec.body_height_mm)
    for line in (spec.mrp, spec.manufacturer, spec.address, spec.consumer_care, spec.mfg_date, *spec.extra_lines):
        if not line:
            continue
        draw.text((x, y), line, font=body, fill=spec.ink)
        y += px(spec.body_height_mm * 2.1)

    # --- reference card (ID-1): light body, dark rim, a chip and a stripe
    cx, cy = margin * 2 + label_w, margin + (max(label_h, card_h) - card_h) // 2
    radius = px(3.18)  # ISO corner radius
    draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=radius, fill=(232, 236, 240), outline=(30, 30, 35), width=3)
    draw.rounded_rectangle([cx + px(8), cy + px(14), cx + px(20), cy + px(23)], radius=px(1), fill=(196, 160, 60))
    draw.rectangle([cx + px(6), cy + card_h - px(14), cx + card_w - px(6), cy + card_h - px(10)], fill=(90, 90, 100))
    draw.text((cx + px(8), cy + px(30)), "4000 1234 5678 9010", font=font_for_cap_mm(3.2), fill=(70, 70, 80))

    bgr = np.array(img)[:, :, ::-1].copy()
    geometry = {
        "mm_per_px": spec.mm_per_px,
        "label_bbox": {"x_min": lx, "y_min": ly, "x_max": lx + label_w, "y_max": ly + label_h},
        "card_bbox": {"x_min": cx, "y_min": cy, "x_max": cx + card_w, "y_max": cy + card_h},
        "pdp_area_cm2": round(spec.label_width_mm * spec.label_height_mm / 100.0, 2),
        "numeral_height_mm": spec.numeral_height_mm,
    }
    return bgr, geometry


# Demo catalogue: each entry is an honest scenario the rule engine should judge.
DEMO_LABELS: list[tuple[str, SyntheticLabel]] = [
    (
        "compliant_biscuits",
        SyntheticLabel(),
    ),
    (
        "missing_tax_phrase",
        SyntheticLabel(
            brand="AMRIT DAIRY",
            product="Pure Cow Ghee",
            net_quantity="Net Quantity: 500 ml",
            mrp="MRP Rs. 320.00",
            manufacturer="Manufactured by: Amrit Dairy Products Ltd",
            address="Survey No 45, Anand, Gujarat 388001",
            consumer_care="Customer care: 1800-266-5544",
            mfg_date="Mfg Date: 07/2026",
            numeral_height_mm=2.6,
        ),
    ),
    (
        "non_metric_unit",
        SyntheticLabel(
            brand="HILLTOP TEA",
            product="Assam Leaf Tea",
            net_quantity="Net Wt. 250 gms",
            mrp="MRP Rs. 180.00 inclusive of all taxes",
            manufacturer="Packed by: Hilltop Beverages Pvt Ltd",
            address="Tea Estate Road, Dibrugarh, Assam 786001",
            consumer_care="Consumer care: feedback@hilltoptea.in",
            mfg_date="Pkd: 06/2026",
        ),
    ),
    (
        "undersized_numerals",
        SyntheticLabel(
            brand="NUTRIMIX",
            product="Family Pack Cereal",
            net_quantity="Net Quantity: 1 kg",
            mrp="MRP Rs. 399.00 (inclusive of all taxes)",
            manufacturer="Mfd by: Nutrimix Foods Limited",
            address="Plot 7, Sector 22, Gurugram, Haryana 122015",
            consumer_care="Toll free: 1800-102-9999",
            mfg_date="Pkd: 09/2026",
            label_width_mm=260.0,
            label_height_mm=220.0,
            numeral_height_mm=1.6,  # 572 cm² panel requires >= 4 mm
            mm_per_px=0.18,
        ),
    ),
    (
        "missing_consumer_care",
        SyntheticLabel(
            brand="COASTAL SNACKS",
            product="Banana Chips",
            net_quantity="Net Quantity: 150 g",
            mrp="MRP Rs. 60.00 (inclusive of all taxes)",
            manufacturer="Mfd by: Coastal Snacks Pvt Ltd",
            address="Industrial Estate, Kozhikode, Kerala 673016",
            consumer_care="",
            mfg_date="Pkd: 09/2026",
        ),
    ),
]
