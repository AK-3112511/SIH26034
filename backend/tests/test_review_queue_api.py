import os
import sys
import uuid
import pytest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID, ENUM
from geoalchemy2 import Geometry

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

from app.db.base import Base
from app.db.session import get_db
from app.models.enums import UserRole, ScanStatus, ScanSource, RuleStatus
from app.models.user import User
from app.models.scan import Scan
from app.models.extracted_field import ExtractedField
from app.models.rule_result import RuleResult
from app.models.audit_log import AuditLog
from app.core.security import get_password_hash, create_access_token
from app.routers import scans, auth
from app.db.seed_scans import seed_pending_review_scans

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@event.listens_for(engine, "connect")
def connect(dbapi_connection, connection_record):
    dbapi_connection.create_function("AsEWKB", 1, lambda x: x)
    dbapi_connection.create_function("AsBinary", 1, lambda x: x)
    dbapi_connection.create_function("GeomFromEWKB", 1, lambda x: x)
    dbapi_connection.create_function("GeomFromEWKT", 1, lambda x: x)
    dbapi_connection.create_function("ST_GeomFromEWKT", 1, lambda x: x)
    dbapi_connection.create_function("AsGeoJSON", 1, lambda x: x)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(scans.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

SENIOR_USER_ID = uuid.uuid4()

@pytest.fixture(autouse=True)
def setup_test_data():
    db = TestingSessionLocal()
    db.query(AuditLog).delete()
    db.query(RuleResult).delete()
    db.query(ExtractedField).delete()
    db.query(Scan).delete()
    db.query(User).delete()

    # Create a senior LMO user for queue access
    senior_user = User(
        id=SENIOR_USER_ID,
        username="senior_officer",
        email="senior@legalmetrology.gov.in",
        hashed_password=get_password_hash("SeniorPass@123"),
        full_name="Senior Officer",
        role=UserRole.SENIOR_LMO,
        district="Chennai",
        is_active=True
    )
    db.add(senior_user)
    db.commit()

    # Seed the standard pending review scans
    seed_pending_review_scans(db)
    db.close()


def get_auth_header():
    token = create_access_token(
        lmo_id=str(SENIOR_USER_ID),
        role=UserRole.SENIOR_LMO.value,
        district="Chennai"
    )
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_stats_from_real_scan_rows():
    """Confirm GET /scans/stats rolls up today's counts from persisted scans."""
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=2)

    passed = Scan(
        scan_id=uuid.uuid4(),
        source=ScanSource.MOBILE.value,
        status=ScanStatus.PASSED.value,
        image_url="/static/uploads/passed.jpg",
        evidence_hash="a" * 64,
        captured_at_utc=now,
        created_at=now,
    )
    failed = Scan(
        scan_id=uuid.uuid4(),
        source=ScanSource.MOBILE.value,
        status=ScanStatus.FAILED.value,
        image_url="/static/uploads/failed.jpg",
        evidence_hash="b" * 64,
        captured_at_utc=now,
        created_at=now,
    )
    old_failed = Scan(
        scan_id=uuid.uuid4(),
        source=ScanSource.MOBILE.value,
        status=ScanStatus.FAILED.value,
        image_url="/static/uploads/old_failed.jpg",
        evidence_hash="c" * 64,
        captured_at_utc=yesterday,
        created_at=yesterday,
    )
    db.add_all([passed, failed, old_failed])
    db.commit()
    db.close()

    resp = client.get("/api/v1/scans/stats", headers=get_auth_header())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["passed_today"] >= 1
    assert data["failed_today"] >= 1
    assert data["scanned_today"] >= data["passed_today"] + data["failed_today"]
    # pending_review is queue depth (not today-only); seed fixture is four PENDING_REVIEW scans
    assert data["pending_review"] >= 4


def test_list_pending_review_scans():
    """Confirm GET /scans/?status=PENDING_REVIEW reads real pending review scans."""
    resp = client.get("/api/v1/scans/?status=PENDING_REVIEW", headers=get_auth_header())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] >= 4
    items = data["items"]

    # Verify fields in items
    for item in items:
        assert item["status"] == "PENDING_REVIEW"
        assert item["product_name"] is not None
        assert item["confidence_gap"] is not None
        assert item["age_hours"] is not None
        assert item["district_label"] in ["Chennai, TN", "Coimbatore, TN", "Madurai, TN", "Salem, TN"]


def test_filter_by_district():
    """Confirm filtering by district returns only matching items."""
    resp_chennai = client.get("/api/v1/scans/?status=PENDING_REVIEW&district=Chennai", headers=get_auth_header())
    assert resp_chennai.status_code == 200
    data_chennai = resp_chennai.json()
    assert data_chennai["total"] == 1
    assert "Parle-G" in data_chennai["items"][0]["product_name"]
    assert "Chennai" in data_chennai["items"][0]["district_label"]

    resp_coimbatore = client.get("/api/v1/scans/?status=PENDING_REVIEW&district=Coimbatore", headers=get_auth_header())
    assert resp_coimbatore.status_code == 200
    data_coimbatore = resp_coimbatore.json()
    assert data_coimbatore["total"] == 1
    assert "Amul" in data_coimbatore["items"][0]["product_name"]


def test_sort_by_confidence_gap():
    """Confirm sorting by confidence gap desc puts largest gap first."""
    resp = client.get(
        "/api/v1/scans/?status=PENDING_REVIEW&sort_by=confidence_gap&sort_dir=desc",
        headers=get_auth_header()
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    gaps = [item["confidence_gap"] for item in items]
    assert gaps == sorted(gaps, reverse=True)


def test_sort_by_age():
    """Confirm sorting by created_at (age) works in both directions."""
    resp_newest = client.get(
        "/api/v1/scans/?status=PENDING_REVIEW&sort_by=created_at&sort_dir=desc",
        headers=get_auth_header()
    )
    assert resp_newest.status_code == 200
    items = resp_newest.json()["items"]
    ages = [item["age_hours"] for item in items]
    assert ages == sorted(ages)  # newest first means smallest age_hours first


def test_filter_by_confidence_band():
    """Confirm confidence_band filters the full result set before pagination."""
    headers = get_auth_header()
    critical = client.get(
        "/api/v1/scans/?status=PENDING_REVIEW&confidence_band=critical",
        headers=headers,
    )
    assert critical.status_code == 200
    assert critical.json()["total"] == 1
    assert "Maggi" in critical.json()["items"][0]["product_name"]

    moderate = client.get(
        "/api/v1/scans/?status=PENDING_REVIEW&confidence_band=moderate",
        headers=headers,
    )
    assert moderate.status_code == 200
    names = [item["product_name"] for item in moderate.json()["items"]]
    assert moderate.json()["total"] == 2
    assert any("Parle-G" in n for n in names)
    assert any("Amul" in n for n in names)

    low = client.get(
        "/api/v1/scans/?status=PENDING_REVIEW&confidence_band=low",
        headers=headers,
    )
    assert low.status_code == 200
    assert low.json()["total"] == 1
    assert "Good Day" in low.json()["items"][0]["product_name"]


def test_filter_by_age_band():
    """Confirm age_band=today keeps <24h scans and excludes the 1d Maggi fixture."""
    headers = get_auth_header()
    today = client.get(
        "/api/v1/scans/?status=PENDING_REVIEW&age_band=today",
        headers=headers,
    )
    assert today.status_code == 200
    names = [item["product_name"] for item in today.json()["items"]]
    assert today.json()["total"] == 3
    assert all("Maggi" not in (n or "") for n in names)

    older = client.get(
        "/api/v1/scans/?status=PENDING_REVIEW&age_band=older",
        headers=headers,
    )
    assert older.status_code == 200
    assert older.json()["total"] == 1
    assert "Maggi" in older.json()["items"][0]["product_name"]


def test_search_by_query():
    """Confirm text search filters by product name or brand."""
    resp = client.get(
        "/api/v1/scans/?status=PENDING_REVIEW&q=Maggi",
        headers=get_auth_header()
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert "Maggi" in data["items"][0]["product_name"]


def test_scan_detail_and_review_decision():
    """Confirm Scan Detail returns all 5 statutory rules, bounding boxes, and review decision works."""
    # List scans to get a real scan_id
    list_resp = client.get("/api/v1/scans/?status=PENDING_REVIEW", headers=get_auth_header())
    scan_id = list_resp.json()["items"][0]["scan_id"]

    # 1. GET /scans/{scan_id} detail
    detail_resp = client.get(f"/api/v1/scans/{scan_id}", headers=get_auth_header())
    assert detail_resp.status_code == 200
    scan_detail = detail_resp.json()
    assert scan_detail["scan_id"] == scan_id
    assert scan_detail["status"] == "PENDING_REVIEW"
    assert len(scan_detail["extracted_fields"]) >= 5
    assert len(scan_detail["rule_results"]) == 5

    # Check that bounding box exists on brand_name
    brand_field = next(f for f in scan_detail["extracted_fields"] if f["field_name"] == "brand_name")
    assert brand_field["bbox"] is not None
    assert "x1" in brand_field["bbox"]

    # Check statutory rule codes
    rule_ids = [r["rule_id"] for r in scan_detail["rule_results"]]
    assert "6.1.a" in rule_ids
    assert "6.1.c" in rule_ids
    assert "6.1.e" in rule_ids
    assert "6.1.g" in rule_ids
    assert "schedule_ii" in rule_ids

    # 2. POST /scans/{scan_id}/review rejection on empty note
    bad_resp = client.post(
        f"/api/v1/scans/{scan_id}/review",
        json={"decision": "PASSED", "reviewer_note": "   "},
        headers=get_auth_header()
    )
    assert bad_resp.status_code == 422  # pydantic validation error

    # 3. Successful review submission with note and field override
    review_resp = client.post(
        f"/api/v1/scans/{scan_id}/review",
        json={
            "decision": "PASSED",
            "reviewer_note": "Visual verification confirmed net quantity font satisfies Schedule II for this PDP area.",
            "overridden_fields": {"net_quantity": "100 g"}
        },
        headers=get_auth_header()
    )
    assert review_resp.status_code == 200
    review_data = review_resp.json()
    assert review_data["new_status"] == "PASSED"
    assert "Visual verification" in review_data["reviewer_note"]

    # 4. Confirm updated state via detail endpoint
    updated_resp = client.get(f"/api/v1/scans/{scan_id}", headers=get_auth_header())
    assert updated_resp.status_code == 200
    updated_detail = updated_resp.json()
    assert updated_detail["status"] == "PASSED"
    qty_field = next(f for f in updated_detail["extracted_fields"] if f["field_name"] == "net_quantity")
    assert qty_field["raw_text"] == "100 g"
    assert qty_field["ocr_confidence"] == 1.0  # marked fully trusted on override


def test_ecommerce_ingest_derived_manual_calibration():
    """Confirm POST /scans/ingest-derived calculates mm_per_px and pdp_area_cm2 from manual dimensions."""
    import io
    from PIL import Image

    # Create dummy 1000x500 image
    img = Image.new("RGB", (1000, 500), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_bytes = buf.getvalue()

    # Package height: 200mm, width: 100mm
    resp = client.post(
        "/api/v1/scans/ingest-derived",
        data={
            "platform": "Blinkit",
            "package_height_mm": "200.0",
            "package_width_mm": "100.0",
            "package_depth_mm": "50.0",
            "declared_net_quantity": "500g",
            "platform_url": "https://blinkit.com/prn/test-item",
        },
        files={"image": ("screenshot.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=get_auth_header()
    )

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "QUEUED"
    scan_id = data["scan_id"]

    # Verify detail returns computed calibration values
    detail_resp = client.get(f"/api/v1/scans/{scan_id}", headers=get_auth_header())
    assert detail_resp.status_code == 200
    scan_data = detail_resp.json()
    assert scan_data["source"] == "ecommerce"

    # mm_per_px should be long_edge_mm (200.0) / max_px (1000) = 0.2
    assert scan_data["mm_per_px"] == pytest.approx(0.2, rel=1e-3)
    # pdp_area_cm2 should be (200 * 100) / 100 = 200.0 cm²
    assert scan_data["pdp_area_cm2"] == pytest.approx(200.0, rel=1e-2)

