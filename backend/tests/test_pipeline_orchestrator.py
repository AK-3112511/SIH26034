from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

import cv2
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from geoalchemy2 import Geometry
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db, set_session_factory
from app.models.audit_log import AuditLog
from app.models.enums import RuleStatus, ScanSource, ScanStatus
from app.models.extracted_field import ExtractedField
from app.models.rule_result import RuleResult
from app.models.scan import Scan
from app.routers import scans
from app.services.pipeline_orchestrator import (
    MasterPipeline,
    PipelineExecutionResult,
    process_queued_scans,
    process_scan,
)
from app.services.rules.evaluators import RuleEvaluationResult
from app.services.rules.gating import (
    FieldVerificationStatus,
    gate_field,
    gate_fields,
    rollup_scan_status,
)
from app.services.storage import get_storage_provider
from app.services.vision.detector import BoundingBox, DetectionResult
from app.services.vision.extraction_pipeline import ExtractionPipeline
from app.services.vision.ocr.deterministic_ocr import DeterministicOCREngine
from app.services.vision.preprocessor import PreprocessingPipeline
from app.services.vision.semantic.base import ExtractedFieldResult
from app.services.vision.semantic.rule_based_mapper import RuleBasedSemanticMapper


# SQLite JSONB / UUID / Geometry mocks for test isolation
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

import geoalchemy2.admin.dialects.sqlite

geoalchemy2.admin.dialects.sqlite.after_create = lambda *args, **kwargs: None
geoalchemy2.admin.dialects.sqlite.before_drop = lambda *args, **kwargs: None

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@event.listens_for(test_engine, "connect")
def connect(dbapi_connection, connection_record):
    dbapi_connection.create_function("AsEWKB", 1, lambda x: x)
    dbapi_connection.create_function("AsBinary", 1, lambda x: x)
    dbapi_connection.create_function("GeomFromEWKB", 1, lambda x: x)
    dbapi_connection.create_function("GeomFromEWKT", 1, lambda x: x)
    dbapi_connection.create_function("ST_GeomFromEWKT", 1, lambda x: x)
    dbapi_connection.create_function("AsGeoJSON", 1, lambda x: x)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
set_session_factory(TestingSessionLocal)
Base.metadata.create_all(bind=test_engine)

app = FastAPI()
app.include_router(scans.router, prefix="/api/v1")

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def override_get_current_user():
    from app.core.security import get_password_hash
    from app.models.enums import UserRole
    from app.models.user import User

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.username == "senior_pipeline").first()
        if user is None:
            user = User(
                username="senior_pipeline",
                email="senior_pipeline@example.gov.in",
                hashed_password=get_password_hash("Secret#123"),
                full_name="Senior Pipeline",
                role=UserRole.SENIOR_LMO,
                district="Chennai",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    db = TestingSessionLocal()
    db.query(AuditLog).delete()
    db.query(RuleResult).delete()
    db.query(ExtractedField).delete()
    db.query(Scan).delete()
    db.commit()
    db.close()


def create_synthetic_test_image(include_card: bool = True) -> np.ndarray:
    """Creates a synthetic 800x600 image with a package and standard ISO reference card."""
    img = np.full((600, 800, 3), 240, dtype=np.uint8)
    # Package area: 100x100 to 500x500
    cv2.rectangle(img, (100, 100), (500, 500), (200, 200, 200), -1)
    if include_card:
        # Reference card (aspect ~1.586, e.g. 158x100 px)
        cv2.rectangle(img, (550, 100), (708, 200), (50, 50, 200), -1)
    return img


class MockDeterministicDetector:
    """Detector for deterministic end-to-end tests."""
    def __init__(self, card_conf: float = 0.95, has_card: bool = True, card_skew: bool = False):
        self.card_conf = card_conf
        self.has_card = has_card
        self.card_skew = card_skew

    def detect(self, image: np.ndarray, reference_object_type: str | None = None) -> DetectionResult:
        package = BoundingBox(
            x_min=100, y_min=100, x_max=500, y_max=500,
            confidence=0.96, label="package_face",
        )
        if not self.has_card:
            return DetectionResult(package_face=package, reference_card=None)

        # Standard card: 856x540 px -> ratio discrepancy 0%
        # Skewed card: 856x400 px -> ratio discrepancy > 20%
        short_w = 400 if self.card_skew else 540
        card = BoundingBox(
            x_min=550, y_min=100, x_max=550 + 856, y_max=100 + short_w,
            confidence=self.card_conf, label="reference_card",
            corners=np.array([
                [550, 100],
                [550 + 856, 100],
                [550 + 856, 100 + short_w],
                [550, 100 + short_w]
            ], dtype=np.float32)
        )
        return DetectionResult(package_face=package, reference_card=card)


# =============================================================================
# 1. Tests for Confidence Gating (§6.1)
# =============================================================================

class TestConfidenceGating:
    """Verifies per-field confidence gating per §6.1."""

    def test_gate_field_above_both_thresholds_is_verified(self):
        f = ExtractedFieldResult(
            field_name="mrp", raw_text="₹50 inclusive of all taxes",
            bbox={"x_min": 10, "y_min": 10, "x_max": 50, "y_max": 30},
            ocr_confidence=0.98, semantic_confidence=0.95,
        )
        assert gate_field(f) == FieldVerificationStatus.VERIFIED

    def test_gate_field_ocr_below_95_is_unverified(self):
        f = ExtractedFieldResult(
            field_name="mrp", raw_text="₹50 inclusive of all taxes",
            bbox={"x_min": 10, "y_min": 10, "x_max": 50, "y_max": 30},
            ocr_confidence=0.94, semantic_confidence=0.95,
        )
        assert gate_field(f) == FieldVerificationStatus.UNVERIFIED

    def test_gate_field_semantic_below_90_is_unverified(self):
        f = ExtractedFieldResult(
            field_name="net_quantity", raw_text="500 g",
            bbox={"x_min": 10, "y_min": 10, "x_max": 50, "y_max": 30},
            ocr_confidence=0.99, semantic_confidence=0.89,
        )
        assert gate_field(f) == FieldVerificationStatus.UNVERIFIED

    def test_gate_field_missing_confidence_is_unverified(self):
        f = ExtractedFieldResult(
            field_name="manufacturer_name", raw_text="Britannia Industries",
            bbox={"x_min": 10, "y_min": 10, "x_max": 50, "y_max": 30},
            ocr_confidence=0.99, semantic_confidence=0.0,
        )
        assert gate_field(f) == FieldVerificationStatus.UNVERIFIED
        assert gate_field(None) == FieldVerificationStatus.UNVERIFIED

    def test_gate_fields_batch_dictionary(self):
        fields = {
            "mrp": ExtractedFieldResult(
                "mrp", "₹50", {"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
                ocr_confidence=0.96, semantic_confidence=0.92
            ),
            "unit": ExtractedFieldResult(
                "unit", "g", {"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
                ocr_confidence=0.80, semantic_confidence=0.95
            ),
        }
        gated = gate_fields(fields)
        assert gated["mrp"] == FieldVerificationStatus.VERIFIED
        assert gated["unit"] == FieldVerificationStatus.UNVERIFIED


# =============================================================================
# 2. Tests for Scan-Level Status Rollup (§6.1)
# =============================================================================

class TestScanStatusRollup:
    """Verifies rollup_scan_status logic per §6.1."""

    def test_rollup_calibration_failed_takes_strict_precedence(self):
        rule_pass = [RuleEvaluationResult(rule_id="6.1.a", status=RuleStatus.PASS, reason="ok", evidence={})]
        status = rollup_scan_status(rule_pass, calibration_status=ScanStatus.CALIBRATION_FAILED)
        assert status == ScanStatus.CALIBRATION_FAILED

    def test_rollup_low_confidence_calibration_takes_precedence(self):
        rule_pass = [RuleEvaluationResult(rule_id="6.1.a", status=RuleStatus.PASS, reason="ok", evidence={})]
        status = rollup_scan_status(rule_pass, calibration_status=ScanStatus.LOW_CONFIDENCE_CALIBRATION)
        assert status == ScanStatus.LOW_CONFIDENCE_CALIBRATION

    def test_rollup_any_failure_results_in_failed(self):
        rules = [
            RuleEvaluationResult(rule_id="6.1.a", status=RuleStatus.PASS, reason="ok", evidence={}),
            RuleEvaluationResult(rule_id="6.1.c", status=RuleStatus.FAIL, reason="bad unit", evidence={}),
            RuleEvaluationResult(rule_id="6.1.e", status=RuleStatus.UNVERIFIED, reason="shaky", evidence={}),
        ]
        status = rollup_scan_status(rules)
        assert status == ScanStatus.FAILED

    def test_rollup_no_failures_with_unverified_results_in_pending_review(self):
        rules = [
            RuleEvaluationResult(rule_id="6.1.a", status=RuleStatus.PASS, reason="ok", evidence={}),
            RuleEvaluationResult(rule_id="6.1.c", status=RuleStatus.PASS, reason="ok", evidence={}),
            RuleEvaluationResult(rule_id="6.1.e", status=RuleStatus.UNVERIFIED, reason="low ocr", evidence={}),
        ]
        status = rollup_scan_status(rules)
        assert status == ScanStatus.PENDING_REVIEW

    def test_rollup_all_rules_and_fields_verified_results_in_passed(self):
        rules = [
            RuleEvaluationResult(rule_id="6.1.a", status=RuleStatus.PASS, reason="ok", evidence={}),
            RuleEvaluationResult(rule_id="6.1.c", status=RuleStatus.PASS, reason="ok", evidence={}),
            RuleEvaluationResult(rule_id="6.1.e", status=RuleStatus.PASS, reason="ok", evidence={}),
            RuleEvaluationResult(rule_id="6.1.g", status=RuleStatus.PASS, reason="ok", evidence={}),
            RuleEvaluationResult(rule_id="schedule_ii", status=RuleStatus.PASS, reason="ok", evidence={}),
        ]
        fields = {
            "mrp": ExtractedFieldResult(
                "mrp", "₹50", {"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
                ocr_confidence=0.99, semantic_confidence=0.95
            )
        }
        status = rollup_scan_status(rules, fields=fields)
        assert status == ScanStatus.PASSED


# =============================================================================
# 3. Tests for MasterPipeline Execution (Phases 3.1 -> 3.5)
# =============================================================================

class TestMasterPipelineExecution:
    """Verifies end-to-end algorithmic flow through MasterPipeline."""

    def test_full_pipeline_compliant_scan_passes(self):
        img = create_synthetic_test_image(include_card=True)
        detector = MockDeterministicDetector(card_conf=0.95, has_card=True)
        preproc = PreprocessingPipeline(detector=detector)
        pipeline = MasterPipeline(preprocessor=preproc)

        result: PipelineExecutionResult = pipeline.execute(img)

        assert result.status == ScanStatus.PASSED
        assert result.preprocessing.is_calibration_successful is True
        assert len(result.fields) >= 8  # 8 mandated declarations + indicative product_name
        assert "net_quantity" in result.fields
        assert result.fields["net_quantity"].font_height_mm is not None
        assert result.pdp_area_cm2 is not None
        assert result.compliance is not None
        assert result.compliance.overall_status == ScanStatus.PASSED
        assert result.compliance.passed_count == 5
        assert result.compliance.failed_count == 0

    def test_full_pipeline_missing_card_halts_at_calibration_failed(self):
        img = create_synthetic_test_image(include_card=False)
        detector = MockDeterministicDetector(has_card=False)
        preproc = PreprocessingPipeline(detector=detector)
        pipeline = MasterPipeline(preprocessor=preproc)

        result = pipeline.execute(img)

        assert result.status == ScanStatus.CALIBRATION_FAILED
        assert result.preprocessing.is_calibration_successful is False
        assert result.extraction is None
        assert result.spatial is None
        assert result.compliance is None

    def test_full_pipeline_dual_edge_skew_yields_low_confidence_calibration(self):
        img = create_synthetic_test_image(include_card=True)
        detector = MockDeterministicDetector(card_conf=0.95, has_card=True, card_skew=True)
        preproc = PreprocessingPipeline(detector=detector)
        pipeline = MasterPipeline(preprocessor=preproc)

        result = pipeline.execute(img)

        assert result.status == ScanStatus.LOW_CONFIDENCE_CALIBRATION
        assert result.preprocessing.status == ScanStatus.LOW_CONFIDENCE_CALIBRATION
        assert result.preprocessing.is_ratio_consistent is False

    def test_full_pipeline_low_confidence_ocr_yields_pending_review(self):
        img = create_synthetic_test_image(include_card=True)
        detector = MockDeterministicDetector(card_conf=0.95, has_card=True)
        preproc = PreprocessingPipeline(detector=detector)

        # Build custom extraction pipeline with low OCR confidence (0.80 < 0.95)
        mock_ocr = DeterministicOCREngine(confidence=0.80)
        sem_mapper = RuleBasedSemanticMapper()
        ext_pipe = ExtractionPipeline(ocr_engine=mock_ocr, semantic_mapper=sem_mapper)

        pipeline = MasterPipeline(preprocessor=preproc, extraction_pipeline=ext_pipe)
        result = pipeline.execute(img)

        assert result.status == ScanStatus.PENDING_REVIEW
        assert result.compliance.overall_status == ScanStatus.PENDING_REVIEW
        assert result.compliance.unverified_count > 0


# =============================================================================
# 4. Tests for Database process_scan and Batch process_queued_scans
# =============================================================================

class TestScanDatabaseProcessing:
    """Verifies process_scan, process_queued_scans, and discrete persistence."""

    def test_process_scan_persists_extracted_fields_and_rules(self):
        db = TestingSessionLocal()
        storage = get_storage_provider()

        # Create synthetic image and upload
        img = create_synthetic_test_image(include_card=True)
        _, img_encoded = cv2.imencode(".jpg", img)
        img_bytes = img_encoded.tobytes()
        img_url = storage.upload_file(img_bytes, "test_biscuit.jpg")

        scan_id = uuid.uuid4()
        scan = Scan(
            scan_id=scan_id,
            source=ScanSource.MOBILE,
            image_url=img_url,
            evidence_hash="mock_hash_12345",
            status=ScanStatus.QUEUED,
        )
        db.add(scan)
        db.commit()

        # Process the scan
        detector = MockDeterministicDetector(card_conf=0.95, has_card=True)
        preproc = PreprocessingPipeline(detector=detector)
        pipeline = MasterPipeline(preprocessor=preproc)

        processed = process_scan(scan_id=scan_id, db=db, pipeline=pipeline)

        assert processed is not None
        assert processed.status == ScanStatus.PASSED
        assert processed.pdp_area_cm2 is not None
        assert processed.ruleset_version is not None

        # Verify extracted_fields persisted in DB
        fields = db.query(ExtractedField).filter(ExtractedField.scan_id == scan_id).all()
        assert len(fields) >= 8
        field_names = {f.field_name for f in fields}
        assert "net_quantity" in field_names
        assert "mrp" in field_names
        assert "manufacturer_name" in field_names

        # Verify rule_results persisted in DB
        rules = db.query(RuleResult).filter(RuleResult.scan_id == scan_id).all()
        assert len(rules) == 5
        rule_ids = {r.rule_id for r in rules}
        assert "6.1.a" in rule_ids
        assert "6.1.c" in rule_ids
        assert "6.1.e" in rule_ids
        assert "6.1.g" in rule_ids
        assert "schedule_ii" in rule_ids

        # Verify audit log recorded
        audit = db.query(AuditLog).filter(AuditLog.target_id == str(scan_id)).first()
        assert audit is not None
        assert audit.action == "SCAN_STATUS_PASSED"
        assert audit.detail["new_status"] == "PASSED"
        assert audit.detail["old_status"] == "QUEUED"

        db.close()

    def test_process_queued_scans_batch_processing(self):
        db = TestingSessionLocal()
        storage = get_storage_provider()

        # Seed 3 queued scans
        detector = MockDeterministicDetector(card_conf=0.95, has_card=True)
        preproc = PreprocessingPipeline(detector=detector)
        pipeline = MasterPipeline(preprocessor=preproc)

        img = create_synthetic_test_image(include_card=True)
        _, img_encoded = cv2.imencode(".jpg", img)
        img_bytes = img_encoded.tobytes()

        for _ in range(3):
            url = storage.upload_file(img_bytes, f"scan_{uuid.uuid4().hex[:6]}.jpg")
            scan = Scan(
                scan_id=uuid.uuid4(),
                source=ScanSource.MOBILE,
                image_url=url,
                evidence_hash="mock_hash",
                status=ScanStatus.QUEUED,
            )
            db.add(scan)
        db.commit()

        # Process all queued scans
        processed = process_queued_scans(limit=10, db=db, pipeline=pipeline)
        assert len(processed) == 3
        for s in processed:
            assert s.status == ScanStatus.PASSED

        # Verify no remaining queued scans
        remaining = db.query(Scan).filter(Scan.status == ScanStatus.QUEUED).count()
        assert remaining == 0

        db.close()


# =============================================================================
# 5. Tests for Scans Router Integration (API Ingestion & Processing Endpoints)
# =============================================================================

class TestScansRouterEndpoints:
    """Verifies REST endpoints for ingestion, synchronous process, and batch processing."""

    def test_api_synchronous_process_endpoint(self):
        db = TestingSessionLocal()
        storage = get_storage_provider()

        img = create_synthetic_test_image(include_card=True)
        _, img_encoded = cv2.imencode(".jpg", img)
        img_bytes = img_encoded.tobytes()
        url = storage.upload_file(img_bytes, "biscuit_packet.jpg")

        scan_id = uuid.uuid4()
        scan = Scan(
            scan_id=scan_id,
            source=ScanSource.MOBILE,
            image_url=url,
            evidence_hash="hash_12345",
            status=ScanStatus.QUEUED,
        )
        db.add(scan)
        db.commit()
        db.close()

        # Call POST /api/v1/scans/{scan_id}/process
        response = client.post(f"/api/v1/scans/{scan_id}/process")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["scan_id"] == str(scan_id)
        assert data["status"] in ("PASSED", "PENDING_REVIEW", "CALIBRATION_FAILED")
        assert len(data["extracted_fields"]) > 0
        assert len(data["rule_results"]) > 0

    def test_api_batch_process_queued_endpoint(self):
        db = TestingSessionLocal()
        storage = get_storage_provider()

        img = create_synthetic_test_image(include_card=True)
        _, img_encoded = cv2.imencode(".jpg", img)
        img_bytes = img_encoded.tobytes()
        url = storage.upload_file(img_bytes, "batch_test.jpg")

        scan_id = uuid.uuid4()
        scan = Scan(
            scan_id=scan_id,
            source=ScanSource.MOBILE,
            image_url=url,
            evidence_hash="hash_batch",
            status=ScanStatus.QUEUED,
        )
        db.add(scan)
        db.commit()
        db.close()

        # Call POST /api/v1/scans/process-queued
        response = client.post("/api/v1/scans/process-queued?limit=5")
        assert response.status_code == 200, response.text
        data = response.json()
        assert len(data) >= 1
        processed_ids = [item["scan_id"] for item in data]
        assert str(scan_id) in processed_ids

    def test_api_ingest_with_background_processing(self):
        img = create_synthetic_test_image(include_card=True)
        _, img_encoded = cv2.imencode(".jpg", img)
        img_bytes = img_encoded.tobytes()

        # Ingest with auto_process=True
        response = client.post(
            "/api/v1/scans/ingest",
            data={
                "lat": "12.9716",
                "lng": "77.5946",
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "device_id": "TEST-DEVICE-01",
                "source": "mobile",
                "auto_process": "true",
            },
            files={"image": ("capture.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        )

        assert response.status_code == 201, response.text
        ingest_data = response.json()
        scan_id = ingest_data["scan_id"]

        # Fetch scan details — background task executed by TestClient
        get_resp = client.get(f"/api/v1/scans/{scan_id}")
        assert get_resp.status_code == 200
        scan_detail = get_resp.json()
        assert scan_detail["scan_id"] == scan_id
        # Scan now has real extracted fields and rule results!
        assert len(scan_detail["extracted_fields"]) >= 8
        assert len(scan_detail["rule_results"]) == 5
        assert scan_detail["status"] in ("PASSED", "PENDING_REVIEW", "CALIBRATION_FAILED")
