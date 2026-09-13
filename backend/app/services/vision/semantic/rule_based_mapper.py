from __future__ import annotations

import re

import numpy as np

from app.services.vision.ocr.base import OCRTextLine
from app.services.vision.semantic.base import (
    ExtractedFieldResult,
)

# Indian 6-digit PIN code regex (does not start with 0)
PINCODE_REGEX = re.compile(r"\b([1-9][0-9]{5})\b")

# Net quantity & Metric unit regexes
NET_QTY_REGEX_EN = re.compile(
    r"(?:net\s*(?:quantity|qty\.?|wt\.?|weight|vol\.?|volume)?[:\s]*)?(\d+(?:\.\d+)?)\s*(kg|g|gm|gms|ml|l|ltr|litres|cm|m)\b",
    re.IGNORECASE,
)
NET_QTY_REGEX_HI = re.compile(
    r"(?:शुद्ध\s*मात्रा[:\s]*)?(\d+(?:\.\d+)?)\s*(ग्राम|किग्रा|मिली|लीटर|मीटर)",
)

# Standard SI / Legal Metric Unit Whitelist
UNIT_NORMALIZATION = {
    "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g", "ग्राम": "g",
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg", "किग्रा": "kg",
    "ml": "ml", "mls": "ml", "millilitre": "ml", "milliliter": "ml", "मिली": "ml",
    "l": "l", "ltr": "l", "litre": "l", "litres": "l", "liter": "l", "लीटर": "l",
    "cm": "cm", "centimetre": "cm", "सेमी": "cm",
    "m": "m", "metre": "m", "meter": "m", "मीटर": "m",
}

# MRP patterns
MRP_REGEX = re.compile(
    r"(?:m\.?r\.?p\.?|max(?:imum)?\s*retail\s*price|rs\.?|₹)[:\s]*([\d,]+(?:\.\d{2})?)\s*(.*)",
    re.IGNORECASE,
)

# Manufacturing / Packaging Date patterns
MFG_DATE_REGEX = re.compile(
    r"(?:mfg(?:\s*date)?|mfd(?:\s*date)?|packed|pkd|date\s*of\s*(?:mfg|pkg|packing))[:\s]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|[0-9]{1,2}[/-][0-9]{2,4}|[A-Za-z]{3}[/-][0-9]{2,4})",
    re.IGNORECASE,
)

# Consumer Care patterns
CONSUMER_CARE_KEYWORDS = ("consumer care", "customer care", "toll free", "feedback", "care@", "helpline")
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_REGEX = re.compile(r"(?:1800[-\s]?[0-9]{3}[-\s]?[0-9]{3,4}|\+?91[-\s]?[6-9][0-9]{9})")

# Manufacturer anchors
MFG_ANCHORS = ("mfg by", "manufactured by", "mfd by", "marketed by", "packed by", "pkd by")
CORP_INDICATORS = ("limited", "ltd", "private limited", "pvt ltd", "industries", "foods", "beverages", "corporation")


class RuleBasedSemanticMapper:
    """
    Engine 2B: High-Precision Deterministic Semantic Mapper.
    Performs prompt-free, deterministic entity extraction and NER over OCRTextLine candidates
    for the 8 Legal Metrology schema fields per PCR 2011.

    Guarantees strict separation of ocr_confidence and semantic_confidence.
    """

    def map_fields(
        self,
        ocr_lines: list[OCRTextLine],
        image: np.ndarray | None = None,
    ) -> dict[str, ExtractedFieldResult]:
        extracted: dict[str, ExtractedFieldResult] = {}

        if not ocr_lines:
            return extracted

        address_line_candidates: list[OCRTextLine] = []

        for line in ocr_lines:
            text = line.text.strip()
            text_lower = text.lower()

            # 1. Net Quantity & Unit Extraction
            if "net_quantity" not in extracted:
                match_en = NET_QTY_REGEX_EN.search(text)
                match_hi = NET_QTY_REGEX_HI.search(text)

                if match_en or match_hi:
                    raw_unit = (match_en.group(2) if match_en else match_hi.group(2)).lower()
                    norm_unit = UNIT_NORMALIZATION.get(raw_unit, raw_unit)

                    extracted["net_quantity"] = ExtractedFieldResult(
                        field_name="net_quantity",
                        raw_text=text,
                        bbox=line.bbox,
                        ocr_confidence=line.confidence,
                        semantic_confidence=0.96 if "net" in text_lower or "मात्रा" in text else 0.88,
                    )

                    extracted["unit"] = ExtractedFieldResult(
                        field_name="unit",
                        raw_text=norm_unit,
                        bbox=line.bbox,
                        ocr_confidence=line.confidence,
                        semantic_confidence=0.98 if raw_unit in UNIT_NORMALIZATION else 0.70,
                    )

            # 2. MRP Declaration
            if "mrp" not in extracted:
                mrp_match = MRP_REGEX.search(text)
                if mrp_match or "mrp" in text_lower or "inclusive of all taxes" in text_lower:
                    # Higher semantic confidence if mandatory phrase is present
                    has_tax_phrase = "inclusive of all taxes" in text_lower or "incl" in text_lower
                    sem_conf = 0.96 if has_tax_phrase else 0.86

                    extracted["mrp"] = ExtractedFieldResult(
                        field_name="mrp",
                        raw_text=text,
                        bbox=line.bbox,
                        ocr_confidence=line.confidence,
                        semantic_confidence=sem_conf,
                    )

            # 3. Manufacturing Date
            if "mfg_date" not in extracted:
                is_mfg_anchor = any(text_lower.startswith(a) for a in MFG_ANCHORS)
                mfg_match = MFG_DATE_REGEX.search(text)
                if not is_mfg_anchor and (
                    mfg_match or any(k in text_lower for k in ("pkd", "packed", "date of mfg", "date of pkg"))
                ):
                    extracted["mfg_date"] = ExtractedFieldResult(
                        field_name="mfg_date",
                        raw_text=text,
                        bbox=line.bbox,
                        ocr_confidence=line.confidence,
                        semantic_confidence=0.92,
                    )

            # 4. Consumer Care Contact
            if "consumer_care" not in extracted:
                has_care_kw = any(k in text_lower for k in CONSUMER_CARE_KEYWORDS)
                has_phone = PHONE_REGEX.search(text)
                has_email = EMAIL_REGEX.search(text)

                if has_care_kw or (has_phone and has_email):
                    extracted["consumer_care"] = ExtractedFieldResult(
                        field_name="consumer_care",
                        raw_text=text,
                        bbox=line.bbox,
                        ocr_confidence=line.confidence,
                        semantic_confidence=0.95 if has_care_kw else 0.85,
                    )

            # 5. PIN Code (6-digit Indian PIN)
            if "pincode" not in extracted:
                pin_match = PINCODE_REGEX.search(text)
                if pin_match:
                    pin_str = pin_match.group(1)
                    extracted["pincode"] = ExtractedFieldResult(
                        field_name="pincode",
                        raw_text=pin_str,
                        bbox=line.bbox,
                        ocr_confidence=line.confidence,
                        semantic_confidence=0.97,
                    )

            # 6. Manufacturer Name
            if "manufacturer_name" not in extracted:
                is_mfg_anchor = any(text_lower.startswith(a) for a in MFG_ANCHORS)
                is_corp = any(c in text_lower for c in CORP_INDICATORS)

                if (is_mfg_anchor and len(text) > 10) or is_corp:
                    extracted["manufacturer_name"] = ExtractedFieldResult(
                        field_name="manufacturer_name",
                        raw_text=text,
                        bbox=line.bbox,
                        ocr_confidence=line.confidence,
                        semantic_confidence=0.95 if (is_mfg_anchor or is_corp) else 0.88,
                    )

            # Address candidate collection
            if any(k in text_lower for k in ("plot", "industrial", "phase", "road", "street", "bengaluru", "mumbai", "delhi", "nagar", "pincode")) or PINCODE_REGEX.search(text):
                address_line_candidates.append(line)

        # 7. Manufacturer Address Resolution
        if "manufacturer_address" not in extracted and address_line_candidates:
            # Join candidate address lines
            combined_text = " ".join(c.text.strip() for c in address_line_candidates)
            avg_ocr_conf = float(np.mean([c.confidence for c in address_line_candidates]))

            # Merged bounding box
            min_x = min(c.bbox["x_min"] for c in address_line_candidates)
            min_y = min(c.bbox["y_min"] for c in address_line_candidates)
            max_x = max(c.bbox["x_max"] for c in address_line_candidates)
            max_y = max(c.bbox["y_max"] for c in address_line_candidates)

            extracted["manufacturer_address"] = ExtractedFieldResult(
                field_name="manufacturer_address",
                raw_text=combined_text,
                bbox={"x_min": min_x, "y_min": min_y, "x_max": max_x, "y_max": max_y},
                ocr_confidence=avg_ocr_conf,
                semantic_confidence=0.91,
            )

        return extracted
