import os
import sys
import uuid
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from geoalchemy2 import Geometry
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


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

from app.core.deps import require_senior_lmo
from app.db.base import Base
from app.db.session import get_db
from app.models.enums import ScanSource, ScanStatus, UserRole
from app.models.scan import Scan
from app.routers import dashboard

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
app.include_router(dashboard.router, prefix="/api/v1")


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class _FakeUser:
    def __init__(self, role: UserRole):
        self.role = role
        self.id = uuid.uuid4()


def _senior_lmo_override():
    return _FakeUser(UserRole.SENIOR_LMO)


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[require_senior_lmo] = _senior_lmo_override
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    db = TestingSessionLocal()
    db.query(Scan).delete()
    db.commit()
    db.close()
    yield


def _make_scan(lat: float, lng: float, status: ScanStatus) -> Scan:
    return Scan(
        scan_id=uuid.uuid4(),
        source=ScanSource.MOBILE,
        image_url="uploads/test.jpg",
        evidence_hash="deadbeef",
        lat=lat,
        lng=lng,
        location=None,
        captured_at_utc=datetime.now(timezone.utc),
        status=status,
    )


def _seed(db, scans):
    for s in scans:
        db.add(s)
    db.commit()


def test_heatmap_clusters_nearby_points_instead_of_sending_raw():
    db = TestingSessionLocal()
    # 5 scans clustered tightly around Chennai — should collapse into ~1 cluster.
    chennai = [
        _make_scan(13.0827 + i * 0.0001, 80.2707 + i * 0.0001, ScanStatus.PASSED)
        for i in range(5)
    ]
    _seed(db, chennai)
    db.close()

    resp = client.get("/api/v1/dashboard/heatmap", params={"zoom": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_points"] == 5
    # Server-side clustering: strictly fewer cluster rows than raw points.
    assert len(data["clusters"]) < 5
    assert len(data["clusters"]) == 1
    assert data["clusters"][0]["count"] == 5
    assert data["clusters"][0]["severity"] == "PASS"


def test_heatmap_severity_reflects_dominant_verdict_per_cell():
    db = TestingSessionLocal()
    scans = [
        _make_scan(28.6139, 77.2090, ScanStatus.FAILED),
        _make_scan(28.6140, 77.2091, ScanStatus.FAILED),
        _make_scan(28.6141, 77.2089, ScanStatus.PASSED),
    ]
    _seed(db, scans)
    db.close()

    resp = client.get("/api/v1/dashboard/heatmap", params={"zoom": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["clusters"]) == 1
    cluster = data["clusters"][0]
    assert cluster["fail_count"] == 2
    assert cluster["pass_count"] == 1
    assert cluster["severity"] == "FAIL"


def test_heatmap_separates_distant_clusters():
    db = TestingSessionLocal()
    scans = [
        _make_scan(13.0827, 80.2707, ScanStatus.PASSED),  # Chennai
        _make_scan(28.6139, 77.2090, ScanStatus.FAILED),  # Delhi
    ]
    _seed(db, scans)
    db.close()

    resp = client.get("/api/v1/dashboard/heatmap", params={"zoom": 8})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["clusters"]) == 2
    severities = {c["severity"] for c in data["clusters"]}
    assert severities == {"PASS", "FAIL"}


def test_heatmap_bbox_filters_out_of_viewport_scans():
    db = TestingSessionLocal()
    scans = [
        _make_scan(13.0827, 80.2707, ScanStatus.PASSED),  # Chennai — inside bbox
        _make_scan(28.6139, 77.2090, ScanStatus.FAILED),  # Delhi — outside bbox
    ]
    _seed(db, scans)
    db.close()

    resp = client.get(
        "/api/v1/dashboard/heatmap",
        params={"zoom": 8, "bbox": "12.0,79.0,14.0,81.0"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_points"] == 1
    assert len(data["clusters"]) == 1
    assert data["clusters"][0]["severity"] == "PASS"


def test_heatmap_malformed_bbox_rejected():
    resp = client.get("/api/v1/dashboard/heatmap", params={"bbox": "not-a-bbox"})
    assert resp.status_code == 422


def test_heatmap_zoom_out_of_range_rejected():
    resp = client.get("/api/v1/dashboard/heatmap", params={"zoom": 99})
    assert resp.status_code == 422


def test_heatmap_requires_senior_lmo_or_admin_role():
    from fastapi import HTTPException, status

    def _reject():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    app.dependency_overrides[require_senior_lmo] = _reject
    try:
        resp = client.get("/api/v1/dashboard/heatmap")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides[require_senior_lmo] = _senior_lmo_override


def test_heatmap_empty_when_no_scans():
    resp = client.get("/api/v1/dashboard/heatmap")
    assert resp.status_code == 200
    data = resp.json()
    assert data["clusters"] == []
    assert data["total_points"] == 0
