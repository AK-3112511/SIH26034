from __future__ import annotations

import uuid

import geoalchemy2.admin.dialects.sqlite
import pytest
from geoalchemy2 import Geometry
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(ENUM, "sqlite")
def compile_enum_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(Geometry, "sqlite")
def compile_geometry_sqlite(type_, compiler, **kw):
    return "TEXT"

geoalchemy2.admin.dialects.sqlite.after_create = lambda *args, **kwargs: None
geoalchemy2.admin.dialects.sqlite.before_drop = lambda *args, **kwargs: None

from app.db.base import Base
from app.models.enums import RuleStatus, ScanSource, ScanStatus
from app.models.rule_result import RuleResult
from app.models.scan import Scan
from app.services.rules.engine import ComplianceRuleEngine, persist_rule_results
from app.services.rules.evaluators import (
    check_consumer_care,
    check_manufacturer_details,
    check_metric_units,
    check_mrp_declaration,
    check_schedule_ii,
)
from app.services.rules.ruleset_config import (
    PLACEHOLDER_SCHEDULE_II_V1,
    STATUTORY_SCHEDULE_II_2011,
    ScheduleIIBand,
    ScheduleIIRuleset,
    register_ruleset,
)
from app.services.vision.semantic.base import ExtractedFieldResult


@pytest.fixture
def compliant_fields() -> dict[str, ExtractedFieldResult]:
    """Returns a full set of legally compliant fields with high confidence."""
    return {
        "manufacturer_name": ExtractedFieldResult(
            field_name="manufacturer_name",
            raw_text="Britannia Industries Limited",
            bbox={"x_min": 50, "y_min": 50, "x_max": 350, "y_max": 80},
            ocr_confidence=0.98,
            semantic_confidence=0.95,
        ),
        "manufacturer_address": ExtractedFieldResult(
            field_name="manufacturer_address",
            raw_text="Plot 14, Whitefield Industrial Area, Bengaluru, Karnataka - 560066",
            bbox={"x_min": 50, "y_min": 90, "x_max": 450, "y_max": 140},
            ocr_confidence=0.97,
            semantic_confidence=0.94,
        ),
        "pincode": ExtractedFieldResult(
            field_name="pincode",
            raw_text="560066",
            bbox={"x_min": 50, "y_min": 90, "x_max": 450, "y_max": 140},
            ocr_confidence=0.97,
            semantic_confidence=0.98,
        ),
        "net_quantity": ExtractedFieldResult(
            field_name="net_quantity",
            raw_text="Net Quantity: 500 g",
            bbox={"x_min": 50, "y_min": 150, "x_max": 250, "y_max": 180},
            ocr_confidence=0.99,
            semantic_confidence=0.96,
            font_height_mm=3.0,
        ),
        "unit": ExtractedFieldResult(
            field_name="unit",
            raw_text="g",
            bbox={"x_min": 50, "y_min": 150, "x_max": 250, "y_max": 180},
            ocr_confidence=0.99,
            semantic_confidence=0.98,
        ),
        "mrp": ExtractedFieldResult(
            field_name="mrp",
            raw_text="MRP Rs. 120.00 (Inclusive of all taxes)",
            bbox={"x_min": 50, "y_min": 190, "x_max": 380, "y_max": 220},
            ocr_confidence=0.98,
            semantic_confidence=0.96,
            font_height_mm=3.0,
        ),
        "consumer_care": ExtractedFieldResult(
            field_name="consumer_care",
            raw_text="Consumer Care: feedback@britannia.co.in / Toll Free 1800-425-4444",
            bbox={"x_min": 50, "y_min": 270, "x_max": 480, "y_max": 300},
            ocr_confidence=0.96,
            semantic_confidence=0.93,
        ),
    }


# ==============================================================================
# 1. Rule 6(1)(a): Manufacturer Details Tests
# ==============================================================================

class TestRule61aManufacturerDetails:
    def test_compliant_manufacturer_passes(self, compliant_fields):
        res = check_manufacturer_details(compliant_fields)
        assert res.rule_id == "6.1.a"
        assert res.status == RuleStatus.PASS
        assert "560066" in res.evidence["pincode"]

    def test_missing_manufacturer_name_fails(self, compliant_fields):
        del compliant_fields["manufacturer_name"]
        res = check_manufacturer_details(compliant_fields)
        assert res.status == RuleStatus.FAIL
        assert "Missing mandatory manufacturer" in res.reason

    def test_missing_pincode_fails(self, compliant_fields):
        # Remove pincode and strip any digits from address
        del compliant_fields["pincode"]
        compliant_fields["manufacturer_address"] = ExtractedFieldResult(
            field_name="manufacturer_address",
            raw_text="Whitefield Industrial Area, Bengaluru, Karnataka",
            bbox={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
            ocr_confidence=0.99,
            semantic_confidence=0.95,
        )
        res = check_manufacturer_details(compliant_fields)
        assert res.status == RuleStatus.FAIL
        assert "Missing valid 6-digit Indian PIN code" in res.reason

    def test_low_confidence_unverified(self, compliant_fields):
        # OCR confidence below 0.95 triggers UNVERIFIED (gating §6.1)
        compliant_fields["manufacturer_name"] = ExtractedFieldResult(
            field_name="manufacturer_name",
            raw_text="Britannia Industries Limited",
            bbox={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
            ocr_confidence=0.88,
            semantic_confidence=0.95,
        )
        res = check_manufacturer_details(compliant_fields)
        assert res.status == RuleStatus.UNVERIFIED
        assert "needs human check" in res.reason


# ==============================================================================
# 2. Rule 6(1)(c): Standard Metric Units Tests
# ==============================================================================

class TestRule61cMetricUnits:
    @pytest.mark.parametrize("valid_unit", ["g", "kg", "ml", "l", "cm", "m"])
    def test_whitelisted_metric_units_pass(self, compliant_fields, valid_unit):
        compliant_fields["net_quantity"] = ExtractedFieldResult(
            field_name="net_quantity",
            raw_text=f"Net Quantity: 100 {valid_unit}",
            bbox={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
            ocr_confidence=0.98,
            semantic_confidence=0.96,
        )
        compliant_fields["unit"] = ExtractedFieldResult(
            field_name="unit",
            raw_text=valid_unit,
            bbox={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
            ocr_confidence=0.98,
            semantic_confidence=0.96,
        )
        res = check_metric_units(compliant_fields)
        assert res.rule_id == "6.1.c"
        assert res.status == RuleStatus.PASS

    def test_prohibited_abbreviation_gms_fails(self, compliant_fields):
        compliant_fields["net_quantity"] = ExtractedFieldResult(
            field_name="net_quantity",
            raw_text="Net Wt. 400 gms",
            bbox={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
            ocr_confidence=0.99,
            semantic_confidence=0.96,
        )
        res = check_metric_units(compliant_fields)
        assert res.status == RuleStatus.FAIL
        assert "Non-standard metric unit symbol 'gms' used" in res.reason

    def test_non_standard_imperial_ounces_fails(self, compliant_fields):
        compliant_fields["net_quantity"] = ExtractedFieldResult(
            field_name="net_quantity",
            raw_text="Net Volume 16 ounces",
            bbox={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
            ocr_confidence=0.99,
            semantic_confidence=0.96,
        )
        res = check_metric_units(compliant_fields)
        assert res.status == RuleStatus.FAIL
        assert "Non-standard metric unit symbol 'ounces' used" in res.reason

    def test_missing_net_quantity_fails(self, compliant_fields):
        del compliant_fields["net_quantity"]
        res = check_metric_units(compliant_fields)
        assert res.status == RuleStatus.FAIL
        assert "Missing mandatory Net Quantity" in res.reason

    def test_low_confidence_unverified(self, compliant_fields):
        compliant_fields["net_quantity"] = ExtractedFieldResult(
            field_name="net_quantity",
            raw_text="Net Quantity: 500 g",
            bbox={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
            ocr_confidence=0.82,  # Below 0.95
            semantic_confidence=0.95,
        )
        res = check_metric_units(compliant_fields)
        assert res.status == RuleStatus.UNVERIFIED


# ==============================================================================
# 3. Rule 6(1)(e): MRP Declaration Tests
# ==============================================================================

class TestRule61eMRPDeclaration:
    def test_tax_inclusive_mrp_passes(self, compliant_fields):
        res = check_mrp_declaration(compliant_fields)
        assert res.rule_id == "6.1.e"
        assert res.status == RuleStatus.PASS

    def test_missing_tax_phrase_fails(self, compliant_fields):
        compliant_fields["mrp"] = ExtractedFieldResult(
            field_name="mrp",
            raw_text="MRP Rs. 120.00",  # Lacks mandatory "inclusive of all taxes"
            bbox={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
            ocr_confidence=0.98,
            semantic_confidence=0.96,
        )
        res = check_mrp_declaration(compliant_fields)
        assert res.status == RuleStatus.FAIL
        assert "lacks the mandatory statutory phrase 'inclusive of all taxes'" in res.reason

    def test_hindi_tax_phrase_passes(self, compliant_fields):
        compliant_fields["mrp"] = ExtractedFieldResult(
            field_name="mrp",
            raw_text="अधिकतम खुदरा मूल्य ₹120 (सभी कर सहित)",
            bbox={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
            ocr_confidence=0.97,
            semantic_confidence=0.95,
        )
        res = check_mrp_declaration(compliant_fields)
        assert res.status == RuleStatus.PASS

    def test_missing_mrp_fails(self, compliant_fields):
        del compliant_fields["mrp"]
        res = check_mrp_declaration(compliant_fields)
        assert res.status == RuleStatus.FAIL


# ==============================================================================
# 4. Rule 6(1)(g): Consumer Care Details Tests
# ==============================================================================

class TestRule61gConsumerCare:
    def test_valid_care_passes(self, compliant_fields):
        res = check_consumer_care(compliant_fields)
        assert res.rule_id == "6.1.g"
        assert res.status == RuleStatus.PASS
        assert res.evidence["has_email"] is True
        assert res.evidence["has_phone"] is True

    def test_missing_care_fails(self, compliant_fields):
        del compliant_fields["consumer_care"]
        res = check_consumer_care(compliant_fields)
        assert res.status == RuleStatus.FAIL

    def test_unusable_care_line_fails(self, compliant_fields):
        compliant_fields["consumer_care"] = ExtractedFieldResult(
            field_name="consumer_care",
            raw_text="For any queries write to us",  # No phone, no email, no address
            bbox={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
            ocr_confidence=0.98,
            semantic_confidence=0.92,
        )
        res = check_consumer_care(compliant_fields)
        assert res.status == RuleStatus.FAIL


# ==============================================================================
# 5. Schedule II: Font Height vs PDP Area Tests (Config-Driven Ruleset)
# ==============================================================================

class TestScheduleIIConfigDriven:
    def test_placeholder_ruleset_notice_present(self):
        ruleset = PLACEHOLDER_SCHEDULE_II_V1
        assert ruleset.is_placeholder is True
        assert "PROVISIONAL PLACEHOLDER RULESET" in ruleset.notice
        assert len(ruleset.bands) == 4

    def test_schedule_ii_pass_small_container(self, compliant_fields):
        # PDP area: 40 cm² (band <= 50 cm², required min 1.5mm)
        # Font height: 2.0mm >= 1.5mm -> PASS
        res = check_schedule_ii(
            fields=compliant_fields,
            font_height_mm=2.0,
            pdp_area_cm2=40.0,
            ruleset=PLACEHOLDER_SCHEDULE_II_V1,
        )
        assert res.rule_id == "schedule_ii"
        assert res.status == RuleStatus.PASS

    def test_schedule_ii_fail_font_too_small(self, compliant_fields):
        # PDP area: 80 cm² (band 50 < Area <= 100 cm², required min 2.0mm)
        # Font height: 1.2mm < 2.0mm -> FAIL
        res = check_schedule_ii(
            fields=compliant_fields,
            font_height_mm=1.2,
            pdp_area_cm2=80.0,
            ruleset=PLACEHOLDER_SCHEDULE_II_V1,
        )
        assert res.status == RuleStatus.FAIL
        assert "Font height 1.20mm is smaller than mandated minimum 2.00mm" in res.reason

    def test_schedule_ii_open_upper_bracket(self, compliant_fields):
        # Statutory Schedule II: PDP area > 2500 cm² requires numerals >= 6.0 mm
        res_pass = check_schedule_ii(compliant_fields, font_height_mm=6.5, pdp_area_cm2=3000.0)
        assert res_pass.status == RuleStatus.PASS

        res_fail = check_schedule_ii(compliant_fields, font_height_mm=4.5, pdp_area_cm2=3000.0)
        assert res_fail.status == RuleStatus.FAIL

        # 500-2500 cm² band requires >= 4.0 mm
        assert check_schedule_ii(compliant_fields, font_height_mm=4.0, pdp_area_cm2=800.0).status == RuleStatus.PASS
        assert check_schedule_ii(compliant_fields, font_height_mm=3.9, pdp_area_cm2=800.0).status == RuleStatus.FAIL

    def test_schedule_ii_missing_measurements_unverified(self, compliant_fields):
        res = check_schedule_ii(compliant_fields, font_height_mm=None, pdp_area_cm2=None)
        assert res.status == RuleStatus.UNVERIFIED

    def test_dynamic_ruleset_switching_without_code_changes(self, compliant_fields):
        """Verifies that legal amendments can be registered as versioned data without changing evaluator code."""
        amended_ruleset = ScheduleIIRuleset(
            version="pcr_2011_amendment_2027",
            effective_date="2027-01-01",
            is_placeholder=False,
            notice="Official gazette amendment",
            bands=[
                ScheduleIIBand(max_area_cm2=100.0, min_font_mm=3.0, description="Strict 3.0mm requirement"),
                ScheduleIIBand(max_area_cm2=None, min_font_mm=5.0, description="Large 5.0mm requirement"),
            ],
        )
        register_ruleset(amended_ruleset)

        # In original ruleset, 2.0mm passed for 40 cm². In amended ruleset (min 3.0mm), 2.0mm must FAIL!
        res_original = check_schedule_ii(compliant_fields, font_height_mm=2.0, pdp_area_cm2=40.0, ruleset=PLACEHOLDER_SCHEDULE_II_V1)
        assert res_original.status == RuleStatus.PASS

        res_amended = check_schedule_ii(compliant_fields, font_height_mm=2.0, pdp_area_cm2=40.0, ruleset=amended_ruleset)
        assert res_amended.status == RuleStatus.FAIL


# ==============================================================================
# 6. Overall Scan Verdict & Master ComplianceRuleEngine Tests
# ==============================================================================

class TestComplianceRuleEngine:
    def test_all_compliant_scan_passes(self, compliant_fields):
        engine = ComplianceRuleEngine()
        eval_result = engine.evaluate(compliant_fields, font_height_mm=3.0, pdp_area_cm2=90.0)

        assert eval_result.overall_status == ScanStatus.PASSED
        assert eval_result.passed_count == 5
        assert eval_result.failed_count == 0
        assert eval_result.unverified_count == 0
        assert len(eval_result.rule_results) == 5

    def test_single_failure_fails_entire_scan(self, compliant_fields):
        # Missing tax phrase in MRP
        compliant_fields["mrp"] = ExtractedFieldResult(
            field_name="mrp",
            raw_text="MRP Rs. 100",
            bbox={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
            ocr_confidence=0.99,
            semantic_confidence=0.96,
        )
        engine = ComplianceRuleEngine()
        eval_result = engine.evaluate(compliant_fields, font_height_mm=3.0, pdp_area_cm2=90.0)

        assert eval_result.overall_status == ScanStatus.FAILED
        assert eval_result.failed_count == 1
        assert eval_result.passed_count == 4

    def test_unverified_field_triggers_pending_review(self, compliant_fields):
        # Low OCR confidence on manufacturer name (no hard failures)
        compliant_fields["manufacturer_name"] = ExtractedFieldResult(
            field_name="manufacturer_name",
            raw_text="Britannia Industries Limited",
            bbox={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
            ocr_confidence=0.85,  # Below 0.95 threshold
            semantic_confidence=0.95,
        )
        engine = ComplianceRuleEngine()
        eval_result = engine.evaluate(compliant_fields, font_height_mm=3.0, pdp_area_cm2=90.0)

        # Must route to human reviewer as PENDING_REVIEW rather than failing product
        assert eval_result.overall_status == ScanStatus.PENDING_REVIEW
        assert eval_result.unverified_count == 1
        assert eval_result.failed_count == 0
        assert eval_result.passed_count == 4


# ==============================================================================
# 7. Database Persistence Tests (§11 `rule_results` table)
# ==============================================================================

def test_discrete_persistence_to_database(compliant_fields):
    """
    CRITICAL INVARIANT TEST (§5.1):
    Every rule result must be persisted individually to rule_results table.
    They must never be collapsed to a single boolean.
    """
    from sqlalchemy import event
    from sqlalchemy.pool import StaticPool

    # SQLite in-memory test database with StaticPool and mock spatial functions
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def connect(dbapi_connection, connection_record):
        dbapi_connection.create_function("GeomFromEWKT", 1, lambda x: x)
        dbapi_connection.create_function("ST_GeomFromEWKT", 1, lambda x: x)
        dbapi_connection.create_function("AsEWKB", 1, lambda x: x)
        dbapi_connection.create_function("AsBinary", 1, lambda x: x)
        dbapi_connection.create_function("GeomFromEWKB", 1, lambda x: x)
        dbapi_connection.create_function("AsGeoJSON", 1, lambda x: x)

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create parent scan
    scan_id = uuid.uuid4()
    scan = Scan(
        scan_id=scan_id,
        source=ScanSource.MOBILE,
        image_url="http://test.local/img.jpg",
        evidence_hash="test_sha256_hash",
        status=ScanStatus.QUEUED,
    )
    session.add(scan)
    session.commit()

    # Evaluate compliance
    rule_engine = ComplianceRuleEngine()
    evaluation = rule_engine.evaluate(compliant_fields, font_height_mm=3.0, pdp_area_cm2=90.0)

    # Persist individual rule results
    persisted = persist_rule_results(session, scan_id, evaluation)
    session.commit()

    assert len(persisted) == 5
    assert scan.status == ScanStatus.PASSED
    assert scan.ruleset_version == STATUTORY_SCHEDULE_II_2011.version

    # Query directly from DB
    db_rows = session.query(RuleResult).filter(RuleResult.scan_id == scan_id).all()
    assert len(db_rows) == 5
    rule_ids = {r.rule_id for r in db_rows}
    assert rule_ids == {"6.1.a", "6.1.c", "6.1.e", "6.1.g", "schedule_ii"}
    assert all(r.status == RuleStatus.PASS for r in db_rows)
