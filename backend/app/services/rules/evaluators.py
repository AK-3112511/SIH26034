from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.models.enums import RuleStatus
from app.services.rules.ruleset_config import ScheduleIIRuleset, get_active_ruleset
from app.services.vision.semantic.base import ExtractedFieldResult

# Statutory minimum confidence thresholds for automated pass/fail (§6.1)
MIN_OCR_CONFIDENCE_THRESHOLD = 0.95
MIN_SEMANTIC_CONFIDENCE_THRESHOLD = 0.90

# Standard SI / Legal Metric Whitelist per Rule 6(1)(c)
LEGAL_METRIC_WHITELIST = {"g", "kg", "ml", "l", "cm", "m"}

# Non-standard abbreviations explicitly prohibited by Rule 6(1)(c)
NON_STANDARD_UNIT_INDICATORS = ("gms", "gm", "grams", "kgs", "kilograms", "mls", "ltr", "litres", "ounces", "lbs")

# 6-digit Indian Postal PIN code regex
PINCODE_REGEX = re.compile(r"\b([1-9][0-9]{5})\b")


@dataclass(frozen=True)
class RuleEvaluationResult:
    """
    Independent pure output of a Legal Metrology PCR 2011 rule evaluation (§5.1).
    Directly maps to the rule_results table in the database schema (§11).
    """
    rule_id: str
    status: RuleStatus
    reason: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "status": self.status.value,
            "reason": self.reason,
            "evidence": self.evidence,
        }


def is_confidence_sufficient(field: ExtractedFieldResult) -> bool:
    """Evaluates per-field confidence gating per §6.1."""
    return (
        field.ocr_confidence >= MIN_OCR_CONFIDENCE_THRESHOLD
        and field.semantic_confidence >= MIN_SEMANTIC_CONFIDENCE_THRESHOLD
    )


def check_manufacturer_details(fields: dict[str, ExtractedFieldResult]) -> RuleEvaluationResult:
    """
    Rule 6(1)(a): Manufacturer Details.
    Validates company name and complete address with a valid 6-digit Indian PIN code.
    Failure: Missing name OR missing 6-digit PIN code.
    """
    mfg_field = fields.get("manufacturer_name")
    addr_field = fields.get("manufacturer_address")
    pin_field = fields.get("pincode")

    if not mfg_field or not mfg_field.raw_text or not mfg_field.raw_text.strip():
        return RuleEvaluationResult(
            rule_id="6.1.a",
            status=RuleStatus.FAIL,
            reason="Missing mandatory manufacturer or packer name declaration",
            evidence={"manufacturer_name": None, "pincode": None},
        )

    # Confidence Gating (§6.1)
    if not is_confidence_sufficient(mfg_field):
        return RuleEvaluationResult(
            rule_id="6.1.a",
            status=RuleStatus.UNVERIFIED,
            reason="Manufacturer name detected but confidence is below statutory threshold (needs human check)",
            evidence={
                "manufacturer_name": mfg_field.raw_text,
                "ocr_confidence": mfg_field.ocr_confidence,
                "semantic_confidence": mfg_field.semantic_confidence,
            },
        )

    # PIN Code Validation
    pin_val: str | None = None
    if pin_field and pin_field.raw_text and PINCODE_REGEX.search(pin_field.raw_text):
        pin_val = PINCODE_REGEX.search(pin_field.raw_text).group(1)
    elif addr_field and addr_field.raw_text and PINCODE_REGEX.search(addr_field.raw_text):
        pin_val = PINCODE_REGEX.search(addr_field.raw_text).group(1)
    elif mfg_field.raw_text and PINCODE_REGEX.search(mfg_field.raw_text):
        pin_val = PINCODE_REGEX.search(mfg_field.raw_text).group(1)

    if not pin_val:
        return RuleEvaluationResult(
            rule_id="6.1.a",
            status=RuleStatus.FAIL,
            reason="Missing valid 6-digit Indian PIN code in manufacturer address",
            evidence={
                "manufacturer_name": mfg_field.raw_text,
                "address": addr_field.raw_text if addr_field else None,
                "pincode": None,
            },
        )

    return RuleEvaluationResult(
        rule_id="6.1.a",
        status=RuleStatus.PASS,
        reason="Manufacturer name and valid 6-digit PIN code verified",
        evidence={
            "manufacturer_name": mfg_field.raw_text,
            "address": addr_field.raw_text if addr_field else None,
            "pincode": pin_val,
            "ocr_confidence": mfg_field.ocr_confidence,
            "semantic_confidence": mfg_field.semantic_confidence,
        },
    )


def check_metric_units(fields: dict[str, ExtractedFieldResult]) -> RuleEvaluationResult:
    """
    Rule 6(1)(c): Standard Metric Units.
    Validates presence of Net Quantity and adherence to legal metric whitelist (g, kg, ml, l, cm, m).
    Failure: Missing Net Qty OR use of non-standard units (e.g. 'gms', 'ounces', 'lbs').
    """
    qty_field = fields.get("net_quantity")
    unit_field = fields.get("unit")

    if not qty_field or not qty_field.raw_text or not qty_field.raw_text.strip():
        return RuleEvaluationResult(
            rule_id="6.1.c",
            status=RuleStatus.FAIL,
            reason="Missing mandatory Net Quantity declaration",
            evidence={"net_quantity": None, "unit": None},
        )

    # Confidence Gating (§6.1)
    if not is_confidence_sufficient(qty_field):
        return RuleEvaluationResult(
            rule_id="6.1.c",
            status=RuleStatus.UNVERIFIED,
            reason="Net quantity detected but confidence is below statutory threshold (needs human check)",
            evidence={
                "net_quantity": qty_field.raw_text,
                "ocr_confidence": qty_field.ocr_confidence,
                "semantic_confidence": qty_field.semantic_confidence,
            },
        )

    raw_text_lower = qty_field.raw_text.lower()

    # Strict check for non-standard abbreviations prohibited by PCR 2011 (e.g. 'gms', 'gm', 'ounces')
    for prohibited in NON_STANDARD_UNIT_INDICATORS:
        # Match whole word to avoid false positives inside words
        if re.search(rf"\b{re.escape(prohibited)}\b", raw_text_lower):
            return RuleEvaluationResult(
                rule_id="6.1.c",
                status=RuleStatus.FAIL,
                reason=f"Non-standard metric unit symbol '{prohibited}' used. PCR 2011 requires standard SI symbols (g, kg, ml, l, cm, m)",
                evidence={
                    "raw_text": qty_field.raw_text,
                    "prohibited_symbol": prohibited,
                    "allowed_symbols": sorted(LEGAL_METRIC_WHITELIST),
                },
            )

    # Verify unit is within the legal whitelist
    normalized_unit = (unit_field.raw_text.lower().strip() if unit_field and unit_field.raw_text else None)
    if not normalized_unit or normalized_unit not in LEGAL_METRIC_WHITELIST:
        return RuleEvaluationResult(
            rule_id="6.1.c",
            status=RuleStatus.FAIL,
            reason=f"Invalid or missing standard metric unit '{normalized_unit}'. Must be one of: {sorted(LEGAL_METRIC_WHITELIST)}",
            evidence={"raw_text": qty_field.raw_text, "unit": normalized_unit},
        )

    return RuleEvaluationResult(
        rule_id="6.1.c",
        status=RuleStatus.PASS,
        reason=f"Valid Net Quantity with standard legal metric unit '{normalized_unit}'",
        evidence={
            "raw_text": qty_field.raw_text,
            "unit": normalized_unit,
            "ocr_confidence": qty_field.ocr_confidence,
            "semantic_confidence": qty_field.semantic_confidence,
        },
    )


def check_mrp_declaration(fields: dict[str, ExtractedFieldResult]) -> RuleEvaluationResult:
    """
    Rule 6(1)(e): MRP Declaration.
    Validates Maximum Retail Price declaration and the mandatory statutory phrase "inclusive of all taxes".
    Failure: Missing MRP OR missing exact tax-inclusive phrase.
    """
    mrp_field = fields.get("mrp")

    if not mrp_field or not mrp_field.raw_text or not mrp_field.raw_text.strip():
        return RuleEvaluationResult(
            rule_id="6.1.e",
            status=RuleStatus.FAIL,
            reason="Missing mandatory Maximum Retail Price (MRP) declaration",
            evidence={"mrp": None},
        )

    # Confidence Gating (§6.1)
    if not is_confidence_sufficient(mrp_field):
        return RuleEvaluationResult(
            rule_id="6.1.e",
            status=RuleStatus.UNVERIFIED,
            reason="MRP detected but confidence is below statutory threshold (needs human check)",
            evidence={
                "mrp": mrp_field.raw_text,
                "ocr_confidence": mrp_field.ocr_confidence,
                "semantic_confidence": mrp_field.semantic_confidence,
            },
        )

    raw_lower = mrp_field.raw_text.lower()
    # Check mandatory statutory clause
    has_tax_phrase = ("inclusive of all taxes" in raw_lower or "incl. of all taxes" in raw_lower or "सभी कर सहित" in raw_lower)

    if not has_tax_phrase:
        return RuleEvaluationResult(
            rule_id="6.1.e",
            status=RuleStatus.FAIL,
            reason="MRP is declared but lacks the mandatory statutory phrase 'inclusive of all taxes'",
            evidence={"raw_text": mrp_field.raw_text, "missing_phrase": "inclusive of all taxes"},
        )

    return RuleEvaluationResult(
        rule_id="6.1.e",
        status=RuleStatus.PASS,
        reason="MRP declared with mandatory 'inclusive of all taxes' phrase",
        evidence={
            "raw_text": mrp_field.raw_text,
            "ocr_confidence": mrp_field.ocr_confidence,
            "semantic_confidence": mrp_field.semantic_confidence,
        },
    )


def check_consumer_care(fields: dict[str, ExtractedFieldResult]) -> RuleEvaluationResult:
    """
    Rule 6(1)(g): Consumer Care Details.
    Validates consumer grievance contact mechanism (telephone helpline, toll-free number, email, or postal address).
    Failure: No valid contact vector found.
    """
    care_field = fields.get("consumer_care")

    if not care_field or not care_field.raw_text or not care_field.raw_text.strip():
        return RuleEvaluationResult(
            rule_id="6.1.g",
            status=RuleStatus.FAIL,
            reason="No valid consumer care contact details found on package",
            evidence={"consumer_care": None},
        )

    # Confidence Gating (§6.1)
    if not is_confidence_sufficient(care_field):
        return RuleEvaluationResult(
            rule_id="6.1.g",
            status=RuleStatus.UNVERIFIED,
            reason="Consumer care details detected but confidence is below statutory threshold (needs human check)",
            evidence={
                "consumer_care": care_field.raw_text,
                "ocr_confidence": care_field.ocr_confidence,
                "semantic_confidence": care_field.semantic_confidence,
            },
        )

    text = care_field.raw_text
    has_email = bool(re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text))
    has_phone = bool(re.search(r"(?:1800[-\s]?[0-9]{3}[-\s]?[0-9]{3,4}|\+?91[-\s]?[6-9][0-9]{9}|\b[0-9]{3,4}[-\s]?[0-9]{6,8}\b)", text))
    has_keyword = any(k in text.lower() for k in ("care", "feedback", "helpline", "toll free", "customer care"))

    if not (has_email or has_phone or has_keyword):
        return RuleEvaluationResult(
            rule_id="6.1.g",
            status=RuleStatus.FAIL,
            reason="Consumer care text present but lacks recognizable phone, email, or helpline contact vectors",
            evidence={"raw_text": text},
        )

    return RuleEvaluationResult(
        rule_id="6.1.g",
        status=RuleStatus.PASS,
        reason="Valid consumer care contact details verified",
        evidence={
            "raw_text": text,
            "has_email": has_email,
            "has_phone": has_phone,
            "ocr_confidence": care_field.ocr_confidence,
            "semantic_confidence": care_field.semantic_confidence,
        },
    )


def check_schedule_ii(
    fields: dict[str, ExtractedFieldResult],
    font_height_mm: float | None,
    pdp_area_cm2: float | None,
    ruleset: ScheduleIIRuleset | None = None,
) -> RuleEvaluationResult:
    """
    Schedule II: Font Height vs PDP Area.
    Evaluates physical font height against the legal step-function defined in the versioned ruleset table.

    Failure: font_height_mm is mathematically smaller than the mandated Schedule II minimum for the container's PDP area.
    Unverified: Physical scale or PDP area measurements are missing.
    """
    active_ruleset = ruleset or get_active_ruleset()

    # Determine target declaration font height (Net Quantity is primary under Schedule II)
    target_font_mm: float | None = font_height_mm
    if target_font_mm is None and "net_quantity" in fields:
        target_font_mm = fields["net_quantity"].font_height_mm

    if target_font_mm is None or pdp_area_cm2 is None or target_font_mm <= 0 or pdp_area_cm2 <= 0:
        return RuleEvaluationResult(
            rule_id="schedule_ii",
            status=RuleStatus.UNVERIFIED,
            reason="Missing spatial measurements (font_height_mm or pdp_area_cm2) required for Schedule II evaluation",
            evidence={
                "font_height_mm": target_font_mm,
                "pdp_area_cm2": pdp_area_cm2,
                "ruleset_version": active_ruleset.version,
            },
        )

    # Apply legal step-function logic from versioned ruleset
    band = active_ruleset.find_matching_band(pdp_area_cm2)

    if target_font_mm < band.min_font_mm:
        return RuleEvaluationResult(
            rule_id="schedule_ii",
            status=RuleStatus.FAIL,
            reason=(
                f"Font height {target_font_mm:.2f}mm is smaller than mandated minimum {band.min_font_mm:.2f}mm "
                f"for PDP area {pdp_area_cm2:.2f}cm² ({band.description})"
            ),
            evidence={
                "measured_font_height_mm": target_font_mm,
                "measured_pdp_area_cm2": pdp_area_cm2,
                "mandated_min_font_mm": band.min_font_mm,
                "matching_band": band.to_dict(),
                "ruleset_version": active_ruleset.version,
                "is_placeholder_ruleset": active_ruleset.is_placeholder,
            },
        )

    return RuleEvaluationResult(
        rule_id="schedule_ii",
        status=RuleStatus.PASS,
        reason=(
            f"Font height {target_font_mm:.2f}mm satisfies required minimum {band.min_font_mm:.2f}mm "
            f"for PDP area {pdp_area_cm2:.2f}cm²"
        ),
        evidence={
            "measured_font_height_mm": target_font_mm,
            "measured_pdp_area_cm2": pdp_area_cm2,
            "mandated_min_font_mm": band.min_font_mm,
            "matching_band": band.to_dict(),
            "ruleset_version": active_ruleset.version,
            "is_placeholder_ruleset": active_ruleset.is_placeholder,
        },
    )
