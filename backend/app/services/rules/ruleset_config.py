from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScheduleIIBand:
    """
    Represents an area bracket and minimum font height requirement under Schedule II.
    max_area_cm2: Upper bound of PDP area in cm² (None indicates open-ended upper bracket).
    min_font_mm: Minimum required font height in millimeters for declarations in this bracket.
    description: Human-readable reference for legal compliance audits.
    """
    max_area_cm2: float | None
    min_font_mm: float
    description: str

    def matches(self, pdp_area_cm2: float) -> bool:
        """Returns True if the PDP area falls into this bracket."""
        if self.max_area_cm2 is None:
            return True
        return pdp_area_cm2 <= self.max_area_cm2

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_area_cm2": self.max_area_cm2,
            "min_font_mm": self.min_font_mm,
            "description": self.description,
        }


@dataclass(frozen=True)
class ScheduleIIRuleset:
    """
    Versioned Schedule II configuration table.
    Enables regulatory amendments to be applied as versioned config data without modifying code.

    IMPORTANT LEGAL NOTICE:
    When is_placeholder=True, the area/font bands are provisional approximations
    and MUST be replaced with verified statutory figures from the Ministry of Consumer
    Affairs prior to any production legal enforcement.
    """
    version: str
    effective_date: str
    is_placeholder: bool
    notice: str
    bands: list[ScheduleIIBand] = field(default_factory=list)

    def find_matching_band(self, pdp_area_cm2: float) -> ScheduleIIBand:
        """
        Applies legal step-function logic to find the first matching band
        where pdp_area_cm2 <= band.max_area_cm2 (or the terminal open-ended band).
        """
        for band in self.bands:
            if band.matches(pdp_area_cm2):
                return band
        # Fallback to the last band if none explicitly matched
        return self.bands[-1]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "effective_date": self.effective_date,
            "is_placeholder": self.is_placeholder,
            "notice": self.notice,
            "bands": [b.to_dict() for b in self.bands],
        }


# ==============================================================================
# Config-Driven Versioned Ruleset Registry
# ==============================================================================

# Initial Version: Clearly labeled placeholder bands per blueprint §5.1 & user instructions
PLACEHOLDER_SCHEDULE_II_V1 = ScheduleIIRuleset(
    version="pcr_2011_schedule_ii_v1_placeholder",
    effective_date="2026-09-01",
    is_placeholder=True,
    notice=(
        "PROVISIONAL PLACEHOLDER RULESET: Area/font brackets are illustrative approximations. "
        "Must be updated with verified statutory figures from the current Legal Metrology "
        "(Packaged Commodities) Rules, 2011 (Schedule II) prior to real-world enforcement."
    ),
    bands=[
        ScheduleIIBand(
            max_area_cm2=50.0,
            min_font_mm=1.5,
            description="Area <= 50 cm²: minimum font height 1.5 mm",
        ),
        ScheduleIIBand(
            max_area_cm2=100.0,
            min_font_mm=2.0,
            description="50 cm² < Area <= 100 cm²: minimum font height 2.0 mm",
        ),
        ScheduleIIBand(
            max_area_cm2=500.0,
            min_font_mm=4.0,
            description="100 cm² < Area <= 500 cm²: minimum font height 4.0 mm",
        ),
        ScheduleIIBand(
            max_area_cm2=None,  # Open-ended upper bracket (> 500 cm²)
            min_font_mm=6.0,
            description="Area > 500 cm²: minimum font height 6.0 mm",
        ),
    ],
)

# Registry of all known versioned rulesets
RULESET_REGISTRY: dict[str, ScheduleIIRuleset] = {
    PLACEHOLDER_SCHEDULE_II_V1.version: PLACEHOLDER_SCHEDULE_II_V1,
}

ACTIVE_RULESET_VERSION = PLACEHOLDER_SCHEDULE_II_V1.version


def get_active_ruleset(version: str | None = None) -> ScheduleIIRuleset:
    """
    Retrieves the requested or active versioned Schedule II ruleset.
    Defaults to the current active ruleset if no version is specified.
    """
    target_version = version or ACTIVE_RULESET_VERSION
    if target_version in RULESET_REGISTRY:
        return RULESET_REGISTRY[target_version]

    # Fallback to current default if unknown version requested
    return RULESET_REGISTRY[ACTIVE_RULESET_VERSION]


def register_ruleset(ruleset: ScheduleIIRuleset) -> None:
    """Dynamically register a new versioned ruleset table (e.g. from DB or admin config)."""
    RULESET_REGISTRY[ruleset.version] = ruleset
