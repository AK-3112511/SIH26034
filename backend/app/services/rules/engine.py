from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.enums import RuleStatus, ScanStatus
from app.models.rule_result import RuleResult
from app.models.scan import Scan
from app.services.rules.evaluators import (
    RuleEvaluationResult,
    check_consumer_care,
    check_manufacturer_details,
    check_metric_units,
    check_mrp_declaration,
    check_schedule_ii,
)
from app.services.rules.gating import rollup_scan_status
from app.services.rules.ruleset_config import ScheduleIIRuleset, get_active_ruleset
from app.services.vision.semantic.base import ExtractedFieldResult

logger = logging.getLogger(__name__)


@dataclass
class ScanComplianceEvaluation:
    """
    Complete compliance evaluation report for an individual inspection scan.
    Maintains every rule result distinctly without collapsing into a single boolean (§5.1).
    """
    overall_status: ScanStatus
    ruleset_version: str
    rule_results: list[RuleEvaluationResult] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.rule_results if r.status == RuleStatus.PASS)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.rule_results if r.status == RuleStatus.FAIL)

    @property
    def unverified_count(self) -> int:
        return sum(1 for r in self.rule_results if r.status == RuleStatus.UNVERIFIED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "ruleset_version": self.ruleset_version,
            "summary": {
                "total_rules": len(self.rule_results),
                "passed": self.passed_count,
                "failed": self.failed_count,
                "unverified": self.unverified_count,
            },
            "results": [r.to_dict() for r in self.rule_results],
        }


class ComplianceRuleEngine:
    """
    Master PCR 2011 Compliance Rule Engine (§5.1 & §6.1).
    Evaluates independent pure functions for each statutory declaration rule and
    computes the definitive legal status without loss of discrete rule evidence.
    """

    def __init__(self, ruleset_version: str | None = None):
        self.ruleset: ScheduleIIRuleset = get_active_ruleset(ruleset_version)

    def evaluate(
        self,
        fields: dict[str, ExtractedFieldResult],
        font_height_mm: float | None = None,
        pdp_area_cm2: float | None = None,
        calibration_status: ScanStatus = ScanStatus.QUEUED,
    ) -> ScanComplianceEvaluation:
        """
        Executes all PCR 2011 legal rules against extracted declarations and spatial calibration.

        Verdict Resolution (§5.1 & §6.1):
        - FAILED: If AT LEAST ONE rule has status FAIL.
        - PENDING_REVIEW: If NO rules failed, but AT LEAST ONE rule is UNVERIFIED (human-in-the-loop).
        - PASSED: If ALL mandatory rules have status PASS.
        """
        results: list[RuleEvaluationResult] = [
            check_manufacturer_details(fields),
            check_metric_units(fields),
            check_mrp_declaration(fields),
            check_consumer_care(fields),
            check_schedule_ii(fields, font_height_mm, pdp_area_cm2, self.ruleset),
        ]

        # Resolve overall scan verdict using statutory rollup logic (§6.1)
        overall = rollup_scan_status(
            rule_results=results,
            fields=fields,
            calibration_status=calibration_status,
        )

        logger.info(
            "Compliance evaluation completed: overall=%s (passed=%d, failed=%d, unverified=%d)",
            overall.value,
            sum(1 for r in results if r.status == RuleStatus.PASS),
            sum(1 for r in results if r.status == RuleStatus.FAIL),
            sum(1 for r in results if r.status == RuleStatus.UNVERIFIED),
        )

        return ScanComplianceEvaluation(
            overall_status=overall,
            ruleset_version=self.ruleset.version,
            rule_results=results,
        )


def persist_rule_results(
    db: Session,
    scan_id: uuid.UUID,
    evaluation: ScanComplianceEvaluation,
) -> list[RuleResult]:
    """
    Persists each discrete RuleEvaluationResult individually to the rule_results table (§11),
    and updates the parent Scan with the overall verdict and ruleset version.
    """
    # 1. Update parent Scan record
    scan = db.query(Scan).filter(Scan.scan_id == scan_id).first()
    if scan:
        scan.status = evaluation.overall_status
        scan.ruleset_version = evaluation.ruleset_version

    # 2. Persist or update each individual rule result
    db_results: list[RuleResult] = []
    for res in evaluation.rule_results:
        # Check existing row (keyed on scan_id + rule_id)
        existing = (
            db.query(RuleResult)
            .filter(RuleResult.scan_id == scan_id, RuleResult.rule_id == res.rule_id)
            .first()
        )
        if existing:
            existing.status = res.status
            existing.reason = res.reason
            existing.evidence = res.evidence
            db_results.append(existing)
        else:
            new_rule = RuleResult(
                scan_id=scan_id,
                rule_id=res.rule_id,
                status=res.status,
                reason=res.reason,
                evidence=res.evidence,
            )
            db.add(new_rule)
            db_results.append(new_rule)

    db.flush()
    return db_results
