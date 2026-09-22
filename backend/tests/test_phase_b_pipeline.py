"""Phase B: real-pipeline plumbing — manual calibration, failure states, measurement."""
from __future__ import annotations

import io
import os
import uuid
from datetime import datetime, timezone

import cv2
import numpy as np
import pytest

from app.models.enums import RuleStatus, ScanSource, ScanStatus, UserRole
from app.models.scan import Scan
from app.services.pipeline_orchestrator import MasterPipeline, process_scan, requeue_stale_processing
from app.services.vision.spatial_calibration import measure_glyph_height_px
from app.services.vision.synthetic import DEMO_LABELS, SyntheticLabel, render_label_with_card

# ---------------------------------------------------------------------------
# Numeral height measurement
# ---------------------------------------------------------------------------

def test_glyph_height_measures_cap_band_not_line_box():
    """A line with descenders must report the digit body height, not the full ink extent."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (600, 120), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 48) if os.path.exists("C:/Windows/Fonts/arial.ttf") else ImageFont.load_default()
    draw.text((10, 20), "Quantity 500 g", font=font, fill="black")
    arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    full_box = {"x_min": 0, "y_min": 0, "x_max": 600, "y_max": 120}
    glyph = measure_glyph_height_px(arr, full_box)
    assert glyph is not None
    # Arial cap height ≈ 0.72 × size ≈ 35 px; descenders would push the raw extent to ~45+ px.
    assert 28 <= glyph <= 40, glyph


def test_glyph_height_returns_none_for_blank_crop():
    blank = np.full((80, 200, 3), 255, np.uint8)
    assert measure_glyph_height_px(blank, {"x_min": 0, "y_min": 0, "x_max": 200, "y_max": 80}) is None


# ---------------------------------------------------------------------------
# Manual (declared-dimension) calibration path
# ---------------------------------------------------------------------------

def test_manual_calibration_skips_card_detection():
    """An e-commerce screenshot has no card; declared dimensions provide the scale."""
    image, _ = render_label_with_card(SyntheticLabel())
    label_only = image[:, : int(image.shape[1] * 0.62)]  # crop the card away
    pipeline = MasterPipeline()
    result = pipeline.execute(label_only, reference_object_type="manual", manual_mm_per_px=0.12, manual_pdp_area_cm2=150.0)
    assert result.status != ScanStatus.CALIBRATION_FAILED
    assert result.preprocessing.reference_card_bbox is None
    assert result.preprocessing.detection_result.engine == "manual"
    assert result.mm_per_px == pytest.approx(0.12)
    assert result.pdp_area_cm2 == pytest.approx(150.0)


def test_without_manual_scale_cardless_image_fails_calibration():
    image, _ = render_label_with_card(SyntheticLabel())
    label_only = image[:, : int(image.shape[1] * 0.62)]
    result = MasterPipeline().execute(label_only, reference_object_type="debit_card")
    assert result.status == ScanStatus.CALIBRATION_FAILED
    assert result.mm_per_px is None


# ---------------------------------------------------------------------------
# Processing state machine
# ---------------------------------------------------------------------------

def _ingest(client, headers, image_bytes, **extra):
    data = {"lat": "13.0827", "lng": "80.2707", "device_id": "D1", "auto_process": "false", "reference_object_type": "debit_card"}
    data.update(extra)
    return client.post(
        "/api/v1/scans/ingest",
        data=data,
        files={"image": ("capture.jpg", io.BytesIO(image_bytes), "image/jpeg")},
        headers=headers,
    )


def test_pipeline_crash_marks_processing_failed(app_client, db_session, make_user, auth_headers, tiny_jpeg, monkeypatch):
    officer = make_user(UserRole.FIELD_LMO)
    scan_id = _ingest(app_client, auth_headers(officer), tiny_jpeg).json()["scan_id"]

    class Boom(MasterPipeline):
        def execute(self, *a, **k):
            raise RuntimeError("simulated model crash")

    result = process_scan(uuid.UUID(scan_id), db=db_session, pipeline=Boom())
    assert result.status == ScanStatus.PROCESSING_FAILED
    assert "simulated model crash" in (result.processing_error or "")

    # A failed scan can be re-run; a definitive verdict cannot be overwritten by the pipeline.
    ok = process_scan(uuid.UUID(scan_id), db=db_session)
    assert ok.status in (ScanStatus.CALIBRATION_FAILED, ScanStatus.PASSED, ScanStatus.FAILED, ScanStatus.PENDING_REVIEW)
    ok.status = ScanStatus.PASSED
    db_session.commit()
    again = process_scan(uuid.UUID(scan_id), db=db_session)
    assert again.status == ScanStatus.PASSED


def test_missing_evidence_file_marks_processing_failed(db_session, make_user):
    officer = make_user(UserRole.FIELD_LMO)
    scan = Scan(
        scan_id=uuid.uuid4(), source=ScanSource.MOBILE, image_url="does_not_exist.jpg", evidence_hash="x",
        lat=1.0, lng=2.0, captured_at_utc=datetime.now(timezone.utc), status=ScanStatus.QUEUED, captured_by_id=officer.id,
    )
    db_session.add(scan)
    db_session.commit()
    out = process_scan(scan.scan_id, db=db_session)
    assert out.status == ScanStatus.PROCESSING_FAILED
    assert "storage" in out.processing_error.lower()


def test_stale_processing_is_requeued(db_session, make_user):
    from datetime import timedelta

    officer = make_user(UserRole.FIELD_LMO)
    old = Scan(
        scan_id=uuid.uuid4(), source=ScanSource.MOBILE, image_url="k.jpg", evidence_hash="x",
        status=ScanStatus.PROCESSING, captured_by_id=officer.id,
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    fresh = Scan(
        scan_id=uuid.uuid4(), source=ScanSource.MOBILE, image_url="k2.jpg", evidence_hash="y",
        status=ScanStatus.PROCESSING, captured_by_id=officer.id, created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([old, fresh])
    db_session.commit()
    assert requeue_stale_processing(db_session) == 1
    db_session.refresh(old)
    db_session.refresh(fresh)
    assert old.status == ScanStatus.QUEUED
    assert fresh.status == ScanStatus.PROCESSING


# ---------------------------------------------------------------------------
# API surface added in Phase B
# ---------------------------------------------------------------------------

def test_districts_endpoint_lists_officer_and_geocoder_districts(app_client, make_user, auth_headers):
    senior = make_user(UserRole.SENIOR_LMO, district="Madurai")
    make_user(UserRole.FIELD_LMO, district="Kanchipuram")
    response = app_client.get("/api/v1/scans/districts", headers=auth_headers(senior))
    assert response.status_code == 200
    districts = response.json()
    assert "Kanchipuram" in districts and "Madurai" in districts and "Chennai, TN" in districts
    field = make_user(UserRole.FIELD_LMO)
    assert app_client.get("/api/v1/scans/districts", headers=auth_headers(field)).status_code == 403


def test_review_blocked_while_processing_and_after_reviewed_verdict(app_client, db_session, make_user, auth_headers, tiny_jpeg):
    senior = make_user(UserRole.SENIOR_LMO)
    admin = make_user(UserRole.ADMIN)
    officer = make_user(UserRole.FIELD_LMO)
    scan_id = _ingest(app_client, auth_headers(officer), tiny_jpeg).json()["scan_id"]
    body = {"decision": "FAILED", "reviewer_note": "Checked by hand"}

    blocked = app_client.post(f"/api/v1/scans/{scan_id}/review", json=body, headers=auth_headers(senior))
    assert blocked.status_code == 409  # still QUEUED

    scan = db_session.query(Scan).filter(Scan.scan_id == uuid.UUID(scan_id)).first()
    scan.status = ScanStatus.PENDING_REVIEW
    db_session.commit()
    first = app_client.post(f"/api/v1/scans/{scan_id}/review", json=body, headers=auth_headers(senior))
    assert first.status_code == 200, first.text

    second = app_client.post(f"/api/v1/scans/{scan_id}/review", json=body, headers=auth_headers(senior))
    assert second.status_code == 409
    by_admin = app_client.post(f"/api/v1/scans/{scan_id}/review", json={**body, "decision": "PASSED"}, headers=auth_headers(admin))
    assert by_admin.status_code == 200


def test_queue_district_filter_uses_capturing_officer(app_client, make_user, auth_headers, tiny_jpeg):
    senior = make_user(UserRole.SENIOR_LMO)
    officer_a = make_user(UserRole.FIELD_LMO, district="Chennai, TN")
    officer_b = make_user(UserRole.FIELD_LMO, district="Madurai")
    _ingest(app_client, auth_headers(officer_a), tiny_jpeg)
    _ingest(app_client, auth_headers(officer_b), tiny_jpeg)

    chennai = app_client.get("/api/v1/scans/?district=chennai", headers=auth_headers(senior)).json()
    assert chennai["total"] == 1 and chennai["items"][0]["district_label"] == "Chennai, TN"
    madurai = app_client.get("/api/v1/scans/?district=Madurai", headers=auth_headers(senior)).json()
    assert madurai["total"] == 1
    everything = app_client.get("/api/v1/scans/?page_size=5", headers=auth_headers(senior)).json()
    assert everything["total"] == 2 and len(everything["items"]) == 2


# ---------------------------------------------------------------------------
# Real OCR end-to-end (opt-in: RUN_PADDLE_TESTS=1 — loads the models, ~1 min)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("RUN_PADDLE_TESTS") != "1", reason="set RUN_PADDLE_TESTS=1 to run the real OCR pipeline")
def test_real_pipeline_reaches_expected_verdicts():
    from app.services.vision.extraction_pipeline import get_extraction_pipeline

    pipeline = MasterPipeline(extraction_pipeline=get_extraction_pipeline(ocr_engine="paddle", semantic_engine="rules"))
    expected = {
        "compliant_biscuits": {ScanStatus.PASSED, ScanStatus.PENDING_REVIEW},
        "missing_tax_phrase": {ScanStatus.PENDING_REVIEW, ScanStatus.FAILED},
        "non_metric_unit": {ScanStatus.FAILED},
        "undersized_numerals": {ScanStatus.FAILED},
        "missing_consumer_care": {ScanStatus.FAILED},
    }
    for name, spec in DEMO_LABELS:
        image, geometry = render_label_with_card(spec)
        result = pipeline.execute(image, reference_object_type="debit_card", product_type="box")
        assert result.status in expected[name], (name, result.status, result.failure_reason)
        assert result.mm_per_px == pytest.approx(geometry["mm_per_px"], rel=0.05)
        qty = result.fields.get("net_quantity")
        assert qty is not None and qty.font_height_mm == pytest.approx(geometry["numeral_height_mm"], rel=0.10)
        if name == "undersized_numerals":
            sched = next(r for r in result.compliance.rule_results if r.rule_id == "schedule_ii")
            assert sched.status == RuleStatus.FAIL
