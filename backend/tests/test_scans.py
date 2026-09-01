import os
import sys
import uuid
import io
import pytest
from datetime import datetime, timezone

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

# Disable Spatialite-specific DDL callbacks for plain SQLite in tests
import geoalchemy2.admin.dialects.sqlite
geoalchemy2.admin.dialects.sqlite.after_create = lambda *args, **kwargs: None
geoalchemy2.admin.dialects.sqlite.before_drop = lambda *args, **kwargs: None

from app.db.base import Base
from app.db.session import get_db
from app.models.scan import Scan
from app.models.extracted_field import ExtractedField
from app.models.rule_result import RuleResult
from app.models.audit_log import AuditLog
from app.models.enums import ScanStatus, ScanSource
from app.services.hash_vault import compute_section_65b_hash, verify_section_65b_hash
from app.routers import scans

# In-memory SQLite database for testing scan ingestion
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Register mock SQLite geometry functions for testing without full Spatialite C library
@event.listens_for(engine, "connect")
def connect(dbapi_connection, connection_record):
    dbapi_connection.create_function("AsEWKB", 1, lambda x: x)
    dbapi_connection.create_function("AsBinary", 1, lambda x: x)
    dbapi_connection.create_function("GeomFromEWKB", 1, lambda x: x)
    dbapi_connection.create_function("GeomFromEWKT", 1, lambda x: x)
    dbapi_connection.create_function("ST_GeomFromEWKT", 1, lambda x: x)
    dbapi_connection.create_function("AsGeoJSON", 1, lambda x: x)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables in test DB
Base.metadata.create_all(bind=engine)

# Build test FastAPI app
app = FastAPI()
app.include_router(scans.router, prefix="/api/v1")

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
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


def test_section_65b_hash_tamper_detection():
    image_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01test_image_bytes_mock"
    lat = 13.0827
    lng = 80.2707
    ts = datetime(2026, 9, 1, 7, 30, 0, tzinfo=timezone.utc)
    device_id = "DEV-LMO-999"

    # Base canonical hash
    base_hash = compute_section_65b_hash(
        image_bytes=image_bytes,
        lat=lat,
        lng=lng,
        captured_at_utc=ts,
        device_id=device_id
    )
    assert len(base_hash) == 64
    assert verify_section_65b_hash(base_hash, image_bytes, lat, lng, ts, device_id) is True

    # Tampering tests — hash must change if any element is modified
    # 1. Tampered GPS Lat
    tampered_lat_hash = compute_section_65b_hash(image_bytes, lat=13.0828, lng=lng, captured_at_utc=ts, device_id=device_id)
    assert tampered_lat_hash != base_hash

    # 2. Tampered Timestamp
    tampered_ts_hash = compute_section_65b_hash(image_bytes, lat=lat, lng=lng, captured_at_utc=datetime(2026, 9, 1, 7, 30, 1, tzinfo=timezone.utc), device_id=device_id)
    assert tampered_ts_hash != base_hash

    # 3. Tampered Device ID
    tampered_dev_hash = compute_section_65b_hash(image_bytes, lat=lat, lng=lng, captured_at_utc=ts, device_id="DEV-LMO-001")
    assert tampered_dev_hash != base_hash

    # 4. Tampered Image Bytes
    tampered_img_hash = compute_section_65b_hash(b"altered_bytes", lat=lat, lng=lng, captured_at_utc=ts, device_id=device_id)
    assert tampered_img_hash != base_hash


def test_scan_ingest_endpoint():
    dummy_img = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00packaged_biscuit_photo"
    ts = datetime(2026, 9, 1, 8, 0, 0, tzinfo=timezone.utc)
    lat = 11.0168
    lng = 76.9558
    device_id = "MOBILE-LMO-COIMBATORE-01"

    expected_hash = compute_section_65b_hash(
        image_bytes=dummy_img,
        lat=lat,
        lng=lng,
        captured_at_utc=ts,
        device_id=device_id
    )

    response = client.post(
        "/api/v1/scans/ingest",
        data={
            "lat": str(lat),
            "lng": str(lng),
            "captured_at_utc": ts.isoformat(),
            "device_id": device_id,
            "reference_object_type": "debit_card",
            "source": "mobile"
        },
        files={"image": ("biscuit.jpg", io.BytesIO(dummy_img), "image/jpeg")}
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert "scan_id" in data
    assert data["status"] == "QUEUED"
    assert data["evidence_hash"] == expected_hash
    assert data["image_url"].startswith("/static/uploads/")

    # Check database persistence
    db = TestingSessionLocal()
    scan = db.query(Scan).filter(Scan.scan_id == uuid.UUID(data["scan_id"])).first()
    assert scan is not None
    assert scan.status == ScanStatus.QUEUED
    assert scan.source == ScanSource.MOBILE
    assert scan.lat == lat
    assert scan.lng == lng
    assert scan.evidence_hash == expected_hash

    # Check audit log entry
    audit = db.query(AuditLog).filter(AuditLog.target_id == str(scan.scan_id)).first()
    assert audit is not None
    assert audit.action == "SCAN_INGESTED"
    assert audit.target_type == "scan"
    assert audit.detail["device_id"] == device_id
    assert audit.detail["status"] == "QUEUED"
    db.close()


def test_get_scan_by_id_roundtrip():
    dummy_img = b"test_image_bytes"
    ts = datetime(2026, 9, 1, 8, 15, 0, tzinfo=timezone.utc)

    ingest_resp = client.post(
        "/api/v1/scans/ingest",
        data={
            "lat": "12.9716",
            "lng": "77.5946",
            "captured_at_utc": ts.isoformat(),
            "device_id": "DEVICE-BLR-01",
            "source": "mobile"
        },
        files={"image": ("product.jpg", io.BytesIO(dummy_img), "image/jpeg")}
    )
    scan_id = ingest_resp.json()["scan_id"]

    # Read back scan by ID
    get_resp = client.get(f"/api/v1/scans/{scan_id}")
    assert get_resp.status_code == 200, get_resp.text
    scan_data = get_resp.json()
    assert scan_data["scan_id"] == scan_id
    assert scan_data["status"] == "QUEUED"
    assert scan_data["source"] == "mobile"
    assert scan_data["lat"] == 12.9716
    assert scan_data["lng"] == 77.5946
    assert scan_data["extracted_fields"] == []
    assert scan_data["rule_results"] == []


def test_get_scan_not_found():
    random_id = uuid.uuid4()
    response = client.get(f"/api/v1/scans/{random_id}")
    assert response.status_code == 404
    assert f"Scan with ID '{random_id}' not found" in response.json()["detail"]
