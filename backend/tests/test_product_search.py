import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

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
from app.models.extracted_field import ExtractedField
from app.models.scan import Scan
from app.routers import products

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
app.include_router(products.router, prefix="/api/v1")


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
    db.query(ExtractedField).delete()
    db.query(Scan).delete()
    db.commit()
    db.close()
    yield


def _make_scan(status: ScanStatus, days_ago: int) -> Scan:
    return Scan(
        scan_id=uuid.uuid4(),
        source=ScanSource.MOBILE,
        image_url="uploads/test.jpg",
        evidence_hash="hash",
        lat=13.08,
        lng=80.27,
        captured_at_utc=datetime.now(timezone.utc) - timedelta(days=days_ago),
        status=status,
    )


def _with_manufacturer(scan: Scan, name: str) -> Scan:
    scan.extracted_fields = [
        ExtractedField(
            id=uuid.uuid4(),
            scan_id=scan.scan_id,
            field_name="manufacturer_name",
            raw_text=name,
            ocr_confidence=0.99,
            semantic_confidence=0.95,
        )
    ]
    return scan


def _seed(db, scans):
    for s in scans:
        db.add(s)
    db.commit()


def test_search_groups_scans_by_manufacturer_name():
    db = TestingSessionLocal()
    scans = [
        _with_manufacturer(_make_scan(ScanStatus.PASSED, 10), "Parle Products Pvt Ltd"),
        _with_manufacturer(_make_scan(ScanStatus.PASSED, 5), "Parle Products Pvt Ltd"),
        _with_manufacturer(_make_scan(ScanStatus.FAILED, 1), "ITC Limited"),
    ]
    _seed(db, scans)
    db.close()

    resp = client.get("/api/v1/products/search")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    names = {r["manufacturer_name"] for r in data["results"]}
    assert names == {"Parle Products Pvt Ltd", "ITC Limited"}
    parle = next(r for r in data["results"] if r["manufacturer_name"] == "Parle Products Pvt Ltd")
    assert parle["total_scans"] == 2
    assert parle["passed_count"] == 2
    assert len(parle["scans"]) == 2


def test_search_query_matches_case_insensitive_substring():
    db = TestingSessionLocal()
    scans = [
        _with_manufacturer(_make_scan(ScanStatus.PASSED, 1), "Parle Products Pvt Ltd"),
        _with_manufacturer(_make_scan(ScanStatus.PASSED, 1), "ITC Limited"),
    ]
    _seed(db, scans)
    db.close()

    resp = client.get("/api/v1/products/search", params={"q": "parle"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["manufacturer_name"] == "Parle Products Pvt Ltd"


def test_search_no_query_returns_all_products_sorted_by_recency():
    db = TestingSessionLocal()
    scans = [
        _with_manufacturer(_make_scan(ScanStatus.PASSED, 30), "Old Corp"),
        _with_manufacturer(_make_scan(ScanStatus.PASSED, 1), "Recent Corp"),
    ]
    _seed(db, scans)
    db.close()

    resp = client.get("/api/v1/products/search")
    assert resp.status_code == 200
    data = resp.json()
    assert [r["manufacturer_name"] for r in data["results"]] == ["Recent Corp", "Old Corp"]


def test_search_excludes_scans_without_manufacturer_name():
    db = TestingSessionLocal()
    # No extracted_fields at all — still QUEUED / unprocessed.
    unprocessed = _make_scan(ScanStatus.QUEUED, 0)
    named = _with_manufacturer(_make_scan(ScanStatus.PASSED, 0), "Amul")
    _seed(db, [unprocessed, named])
    db.close()

    resp = client.get("/api/v1/products/search")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["manufacturer_name"] == "Amul"


def test_trend_improving_when_recent_half_passes_more_than_older_half():
    db = TestingSessionLocal()
    name = "Trend Corp"
    scans = [
        _with_manufacturer(_make_scan(ScanStatus.FAILED, 40), name),
        _with_manufacturer(_make_scan(ScanStatus.FAILED, 30), name),
        _with_manufacturer(_make_scan(ScanStatus.PASSED, 5), name),
        _with_manufacturer(_make_scan(ScanStatus.PASSED, 1), name),
    ]
    _seed(db, scans)
    db.close()

    resp = client.get("/api/v1/products/search", params={"q": name})
    result = resp.json()["results"][0]
    assert result["trend"] == "IMPROVING"
    assert result["pass_rate"] == 0.5


def test_trend_worsening_when_recent_half_fails_more_than_older_half():
    db = TestingSessionLocal()
    name = "Decline Corp"
    scans = [
        _with_manufacturer(_make_scan(ScanStatus.PASSED, 40), name),
        _with_manufacturer(_make_scan(ScanStatus.PASSED, 30), name),
        _with_manufacturer(_make_scan(ScanStatus.FAILED, 5), name),
        _with_manufacturer(_make_scan(ScanStatus.FAILED, 1), name),
    ]
    _seed(db, scans)
    db.close()

    resp = client.get("/api/v1/products/search", params={"q": name})
    result = resp.json()["results"][0]
    assert result["trend"] == "WORSENING"


def test_trend_insufficient_data_with_fewer_than_two_decided_scans():
    db = TestingSessionLocal()
    name = "New Corp"
    scans = [_with_manufacturer(_make_scan(ScanStatus.PENDING_REVIEW, 1), name)]
    _seed(db, scans)
    db.close()

    resp = client.get("/api/v1/products/search", params={"q": name})
    result = resp.json()["results"][0]
    assert result["trend"] == "INSUFFICIENT_DATA"
    assert result["pass_rate"] is None


def test_search_pagination():
    db = TestingSessionLocal()
    scans = [
        _with_manufacturer(_make_scan(ScanStatus.PASSED, i), f"Brand {i}") for i in range(5)
    ]
    _seed(db, scans)
    db.close()

    resp = client.get("/api/v1/products/search", params={"page": 1, "page_size": 2})
    data = resp.json()
    assert data["total"] == 5
    assert len(data["results"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


def test_search_requires_senior_lmo_or_admin_role():
    from fastapi import HTTPException, status

    def _reject():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    app.dependency_overrides[require_senior_lmo] = _reject
    try:
        resp = client.get("/api/v1/products/search")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides[require_senior_lmo] = _senior_lmo_override


def test_search_empty_db_returns_empty_results():
    resp = client.get("/api/v1/products/search")
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"] == []
    assert data["total"] == 0
