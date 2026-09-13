"""PCR 2011 Compliance Rule Engine Subsystem (§5 & §6.1)"""

from app.services.rules.engine import (
    ComplianceRuleEngine,
    ScanComplianceEvaluation,
    persist_rule_results,
)
from app.services.rules.evaluators import (
    LEGAL_METRIC_WHITELIST,
    MIN_OCR_CONFIDENCE_THRESHOLD,
    MIN_SEMANTIC_CONFIDENCE_THRESHOLD,
    RuleEvaluationResult,
    check_consumer_care,
    check_manufacturer_details,
    check_metric_units,
    check_mrp_declaration,
    check_schedule_ii,
)
from app.services.rules.gating import (
    FieldVerificationStatus,
    gate_field,
    gate_fields,
    rollup_scan_status,
)
from app.services.rules.ruleset_config import (
    PLACEHOLDER_SCHEDULE_II_V1,
    ScheduleIIBand,
    ScheduleIIRuleset,
    get_active_ruleset,
    register_ruleset,
)

__all__ = [
    "ComplianceRuleEngine",
    "ScanComplianceEvaluation",
    "persist_rule_results",
    "RuleEvaluationResult",
    "check_manufacturer_details",
    "check_metric_units",
    "check_mrp_declaration",
    "check_consumer_care",
    "check_schedule_ii",
    "LEGAL_METRIC_WHITELIST",
    "MIN_OCR_CONFIDENCE_THRESHOLD",
    "MIN_SEMANTIC_CONFIDENCE_THRESHOLD",
    "FieldVerificationStatus",
    "gate_field",
    "gate_fields",
    "rollup_scan_status",
    "ScheduleIIBand",
    "ScheduleIIRuleset",
    "get_active_ruleset",
    "register_ruleset",
    "PLACEHOLDER_SCHEDULE_II_V1",
]
