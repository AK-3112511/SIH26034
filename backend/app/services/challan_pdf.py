"""Section 39 notice (challan) PDF rendering.

Chain of custody (blueprint §7.2): the original evidence image is placed on
the page untouched; the annotated view is a *separate* copy with vector
rectangles drawn over it at render time.  Boxes are never burned into pixels.
The Section 65B image hash and the PDF's own hash are both printed.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# Design-system tokens (MetrologyAI_Design_System.md §2)
INK_900 = colors.HexColor("#12203B")
INK_600 = colors.HexColor("#3C4E70")
PAPER_100 = colors.HexColor("#F1F3F1")
BRASS_500 = colors.HexColor("#A6742C")
VERDICT_FAIL = colors.HexColor("#B3261E")
VERDICT_PASS = colors.HexColor("#1E7A4D")
VERDICT_NEUTRAL = colors.HexColor("#6B7280")

RULE_TITLES = {
    "6.1.a": "Rule 6(1)(a) — Name and address of manufacturer / packer / importer",
    "6.1.c": "Rule 6(1)(c) — Net quantity in standard units",
    "6.1.e": "Rule 6(1)(e) — Retail sale price (MRP) inclusive of all taxes",
    "6.1.g": "Rule 6(1)(g) — Consumer care details",
    "schedule_ii": "Rule 7(3) / Schedule II — Minimum height of numerals",
}

FIELD_TITLES = {
    "product_name": "Product / brand",
    "net_quantity": "Net quantity",
    "unit": "Unit",
    "mrp": "Retail sale price (MRP)",
    "mfg_date": "Date of manufacture / packing",
    "manufacturer_name": "Manufacturer / packer",
    "manufacturer_address": "Address",
    "pincode": "PIN code",
    "consumer_care": "Consumer care",
}


@dataclass
class ChallanContext:
    scan_id: str
    product_name: str | None
    source: str
    platform: str | None
    captured_at: datetime | None
    lat: float | None
    lng: float | None
    district: str | None
    officer_name: str
    officer_id: str
    issuing_officer_name: str
    evidence_hash: str
    ruleset_version: str | None
    mm_per_px: float | None
    pdp_area_cm2: float | None
    fields: list[dict[str, Any]]  # {field_name, raw_text, font_height_mm, bbox, failed}
    violations: list[dict[str, Any]]  # {rule_id, reason, evidence}
    image_bytes: bytes


def normalise_bbox(bbox: Any) -> tuple[float, float, float, float] | None:
    """Return (x, y, w, h) in source pixels for any stored bbox shape."""
    if not bbox:
        return None
    if isinstance(bbox, dict):
        if {"x_min", "y_min", "x_max", "y_max"} <= set(bbox):
            return (bbox["x_min"], bbox["y_min"], bbox["x_max"] - bbox["x_min"], bbox["y_max"] - bbox["y_min"])
        if {"x1", "y1", "x2", "y2"} <= set(bbox):
            return (bbox["x1"], bbox["y1"], bbox["x2"] - bbox["x1"], bbox["y2"] - bbox["y1"])
        if {"x", "y", "w", "h"} <= set(bbox):
            return (bbox["x"], bbox["y"], bbox["w"], bbox["h"])
        return None
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4 and all(isinstance(v, (int, float)) for v in bbox):
        return tuple(float(v) for v in bbox)  # type: ignore[return-value]
    return None


def _wrap(text: str, font: str, size: int, max_width: float, pdf: canvas.Canvas) -> list[str]:
    words = (text or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if pdf.stringWidth(trial, font, size) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _seal(pdf: canvas.Canvas, cx: float, cy: float, radius: float, label: str, verdict_color) -> None:
    """Double-ring seal badge (design system §5.1) as vector graphics."""
    pdf.saveState()
    pdf.setLineWidth(1.2)
    pdf.setStrokeColor(BRASS_500)
    pdf.circle(cx, cy, radius, stroke=1, fill=0)
    pdf.setStrokeColor(verdict_color)
    pdf.setFillColor(colors.Color(verdict_color.red, verdict_color.green, verdict_color.blue, alpha=0.12))
    pdf.circle(cx, cy, radius * 0.82, stroke=1, fill=1)
    pdf.setFillColor(verdict_color)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawCentredString(cx, cy - 3, label)
    pdf.restoreState()


def _ruler(pdf: canvas.Canvas, x: float, y: float, width: float) -> None:
    """Calibration tick rule (design system §1)."""
    pdf.saveState()
    pdf.setStrokeColor(BRASS_500)
    pdf.setLineWidth(0.6)
    pdf.line(x, y, x + width, y)
    tick = 0
    while tick <= width:
        h = 4 if (tick / 8) % 5 == 0 else 2
        pdf.line(x + tick, y, x + tick, y + h)
        tick += 8
    pdf.restoreState()


def render_challan_pdf(ctx: ChallanContext) -> bytes:
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    pdf.setTitle(f"Section 39 Notice — {ctx.scan_id}")
    width, height = A4
    margin = 42
    content_w = width - 2 * margin
    y = height - margin

    # --- Government header block
    pdf.setFillColor(INK_900)
    pdf.rect(0, height - 92, width, 92, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(margin, height - 38, "GOVERNMENT OF INDIA · DEPARTMENT OF CONSUMER AFFAIRS")
    pdf.setFont("Helvetica", 10.5)
    pdf.drawString(margin, height - 56, "Legal Metrology Enforcement · Notice under Section 39, Legal Metrology Act, 2009")
    pdf.setFont("Helvetica", 8.5)
    pdf.drawString(margin, height - 72, "Legal Metrology (Packaged Commodities) Rules, 2011 — compliance inspection record")
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawRightString(width - margin, height - 40, f"Notice ref: {ctx.scan_id[:8].upper()}")
    pdf.setFont("Helvetica", 8.5)
    pdf.drawRightString(width - margin, height - 56, f"Generated {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')}")
    y = height - 92 - 18

    _seal(pdf, width - margin - 30, y - 22, 26, "VIOLATION", VERDICT_FAIL)

    # --- Particulars
    pdf.setFillColor(INK_900)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margin, y, "1. Particulars of inspection")
    y -= 6
    _ruler(pdf, margin, y, content_w - 80)
    y -= 16
    pdf.setFont("Helvetica", 9.5)
    when = ctx.captured_at.strftime("%d %b %Y, %H:%M UTC") if ctx.captured_at else "not recorded"
    if ctx.lat is not None and ctx.lng is not None:
        where = f"{ctx.lat:.6f}, {ctx.lng:.6f}" + (f" ({ctx.district})" if ctx.district else "")
    else:
        where = f"Online listing — {ctx.platform or 'e-commerce platform'} (no physical premises)"
    rows = [
        ("Commodity", ctx.product_name or "Not declared"),
        ("Captured on", when),
        ("Location", where),
        ("Source", "Field inspection (mobile capture)" if ctx.source == "mobile" else "E-commerce listing (web portal)"),
        ("Inspecting officer", f"{ctx.officer_name}  ·  ID {ctx.officer_id[:8].upper()}"),
        ("Issuing officer", ctx.issuing_officer_name),
        ("Ruleset applied", ctx.ruleset_version or "—"),
    ]
    for label, value in rows:
        pdf.setFillColor(INK_600)
        pdf.drawString(margin, y, label)
        pdf.setFillColor(INK_900)
        for i, line in enumerate(_wrap(value, "Helvetica", 9.5, content_w - 150, pdf)):
            pdf.drawString(margin + 130, y - i * 12, line)
        y -= 12 * max(1, len(_wrap(value, "Helvetica", 9.5, content_w - 150, pdf))) + 2

    # --- Violations
    y -= 10
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margin, y, "2. Contraventions established")
    y -= 6
    _ruler(pdf, margin, y, content_w)
    y -= 16
    for v in ctx.violations:
        title = RULE_TITLES.get(v["rule_id"], v["rule_id"])
        pdf.setFillColor(VERDICT_FAIL)
        pdf.setFont("Helvetica-Bold", 9.5)
        pdf.drawString(margin, y, "•")
        pdf.drawString(margin + 10, y, title)
        y -= 12
        pdf.setFillColor(INK_900)
        pdf.setFont("Helvetica", 9)
        for line in _wrap(v.get("reason") or "", "Helvetica", 9, content_w - 12, pdf):
            pdf.drawString(margin + 10, y, line)
            y -= 11
        y -= 4

    # --- Measured declarations
    y -= 6
    pdf.setFont("Helvetica-Bold", 11)
    pdf.setFillColor(INK_900)
    pdf.drawString(margin, y, "3. Declarations as extracted and measured")
    y -= 6
    _ruler(pdf, margin, y, content_w)
    y -= 14
    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.setFillColor(INK_600)
    pdf.drawString(margin, y, "Declaration")
    pdf.drawString(margin + 130, y, "Text on package")
    pdf.drawRightString(width - margin, y, "Measured height")
    y -= 4
    pdf.setStrokeColor(INK_600)
    pdf.setLineWidth(0.3)
    pdf.line(margin, y, width - margin, y)
    y -= 11
    pdf.setFont("Helvetica", 8.5)
    for f in ctx.fields:
        if f["field_name"] in ("unit", "declared_dimensions"):
            continue
        pdf.setFillColor(VERDICT_FAIL if f.get("failed") else INK_900)
        pdf.drawString(margin, y, FIELD_TITLES.get(f["field_name"], f["field_name"]))
        text_lines = _wrap(f.get("raw_text") or "—", "Helvetica", 8.5, content_w - 210, pdf)[:2]
        for i, line in enumerate(text_lines):
            pdf.drawString(margin + 130, y - i * 10, line)
        height_mm = f.get("font_height_mm")
        pdf.setFont("Courier", 8.5)
        pdf.drawRightString(width - margin, y, f"{height_mm:.2f} mm" if height_mm else "—")
        pdf.setFont("Helvetica", 8.5)
        y -= 10 * len(text_lines) + 3
    pdf.setFillColor(INK_600)
    pdf.setFont("Courier", 8)
    calib = f"Scale {ctx.mm_per_px:.4f} mm/px" if ctx.mm_per_px else "Scale not established"
    pdp = f"Principal display panel {ctx.pdp_area_cm2:.1f} cm²" if ctx.pdp_area_cm2 else ""
    pdf.drawString(margin, y - 2, f"{calib}   {pdp}".strip())

    # --- Evidence page
    pdf.showPage()
    y = height - margin
    pdf.setFillColor(INK_900)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margin, y, "4. Photographic evidence")
    y -= 6
    _ruler(pdf, margin, y, content_w)
    y -= 14

    img = PILImage.open(io.BytesIO(ctx.image_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    img_w, img_h = img.size
    # The embedded copies are for legibility; the original bytes stay in
    # storage under the hash.  Cap the resolution to keep the notice small.
    longest = max(img_w, img_h)
    if longest > 1400:
        factor = 1400 / longest
        img = img.resize((int(img_w * factor), int(img_h * factor)))
    reader = ImageReader(img)
    slot_w = (content_w - 12) / 2
    scale = min(slot_w / img_w, (height * 0.45) / img_h)
    draw_w, draw_h = img_w * scale, img_h * scale

    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(INK_600)
    pdf.drawString(margin, y, "Original (unaltered, hashed)")
    pdf.drawString(margin + slot_w + 12, y, "Annotated copy (vector overlay, not part of evidence bytes)")
    y -= 6
    top = y - draw_h
    pdf.drawImage(reader, margin, top, width=draw_w, height=draw_h)
    ax = margin + slot_w + 12
    pdf.drawImage(reader, ax, top, width=draw_w, height=draw_h)

    pdf.setLineWidth(1.2)
    for f in ctx.fields:
        box = normalise_bbox(f.get("bbox"))
        if box is None:
            continue
        bx, by, bw, bh = box
        if bx <= 1 and by <= 1 and bw <= 1 and bh <= 1:  # normalised 0..1 boxes
            bx, by, bw, bh = bx * img_w, by * img_h, bw * img_w, bh * img_h
        pdf.setStrokeColor(VERDICT_FAIL if f.get("failed") else INK_600)
        pdf.rect(ax + bx * scale, top + draw_h - (by + bh) * scale, bw * scale, bh * scale, stroke=1, fill=0)

    y = top - 22
    pdf.setFillColor(INK_900)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margin, y, "5. Integrity (Section 65B, Indian Evidence Act, 1872)")
    y -= 6
    _ruler(pdf, margin, y, content_w)
    y -= 14
    pdf.setFont("Helvetica", 8.5)
    pdf.setFillColor(INK_600)
    for line in _wrap(
        "The evidence hash below is SHA-256 over the original image bytes concatenated with the GPS "
        "coordinates, capture timestamp and device identifier at the moment of ingestion. Recomputing it "
        "from the stored original must reproduce this value; any alteration of pixels or metadata changes it.",
        "Helvetica", 8.5, content_w, pdf,
    ):
        pdf.drawString(margin, y, line)
        y -= 11
    y -= 4
    pdf.setFont("Courier", 8)
    pdf.setFillColor(INK_900)
    pdf.drawString(margin, y, "Evidence hash:")
    pdf.drawString(margin + 90, y, ctx.evidence_hash[:64])
    y -= 12
    pdf.drawString(margin, y, "Document hash:")
    pdf.drawString(margin + 90, y, "(SHA-256 of this PDF is recorded in the challan register on issue)")

    y -= 40
    pdf.setFont("Helvetica", 8.5)
    pdf.setFillColor(INK_600)
    for line in _wrap(
        "This notice is issued under Section 39 of the Legal Metrology Act, 2009 on the basis of the "
        "contraventions listed in section 2. The verdict was reached by deterministic evaluation of the "
        "Legal Metrology (Packaged Commodities) Rules, 2011 against declarations extracted from the "
        "photograph; a senior Legal Metrology Officer reviewed and confirmed the outcome before issue.",
        "Helvetica", 8.5, content_w, pdf,
    ):
        pdf.drawString(margin, y, line)
        y -= 11
    y -= 30
    pdf.setStrokeColor(INK_900)
    pdf.line(width - margin - 180, y, width - margin, y)
    pdf.drawRightString(width - margin, y - 11, "Signature of issuing officer")

    pdf.save()
    return buf.getvalue()
