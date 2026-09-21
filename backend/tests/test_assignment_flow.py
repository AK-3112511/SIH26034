"""Phase 7.3: Automated tests for E-Commerce -> Field Task Assignment Flow per §5.3.

Verifies:
1. GET /api/v1/users/field-officers lists field LMOs and filters by district
2. Non-senior officers cannot access user assignment directory
3. POST /api/v1/events/task-assigned assigns scan to field officer and emits task.assigned event
4. GET /api/v1/scans/assigned-to-me returns assigned tasks for authenticated field officer
"""
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geoalchemy2 import Geometry

# SQLite in-memory type compilation overrides
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

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db.session import get_db
from app.models.enums import RuleStatus, ScanSource, ScanStatus, UserRole
from app.models.event import EventLog
from app.models.extracted_field import ExtractedField
from app.models.rule_result import RuleResult
from app.models.scan import Scan
from app.models.user import User
from app.routers import events, scans, users

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
app.include_router(users.router, prefix="/api/v1")
app.include_router(scans.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")

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
    db.query(EventLog).delete()
    db.query(RuleResult).delete()
    db.query(ExtractedField).delete()
    db.query(Scan).delete()
    db.query(User).delete()
    db.commit()
    db.close()
    yield

def _make_user(db, username, role, district="Madurai"):
    u = User(
        id=uuid.uuid4(),
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("Secret123#"),
        full_name=f"Officer {username.capitalize()}",
        role=role,
        district=district,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

def _auth_header(user):
    token = create_access_token(
        lmo_id=str(user.id),
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        district=user.district,
    )
    return {"Authorization": f"Bearer {token}"}

def test_users_field_officers_list_and_district_filter():
    db = TestingSessionLocal()
    senior = _make_user(db, "senior_priya", UserRole.SENIOR_LMO, district="Madurai")
    field1 = _make_user(db, "lmo_ramesh", UserRole.FIELD_LMO, district="Madurai")
    field2 = _make_user(db, "lmo_suresh", UserRole.FIELD_LMO, district="Coimbatore")

    # 1. Senior LMO queries all field officers
    res = client.get("/api/v1/users/field-officers", headers=_auth_header(senior))
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    usernames = [u["username"] for u in data]
    assert "lmo_ramesh" in usernames
    assert "lmo_suresh" in usernames

    # 2. Query with district filter
    res_madurai = client.get("/api/v1/users/field-officers?district=Madurai", headers=_auth_header(senior))
    assert res_madurai.status_code == 200
    data_madurai = res_madurai.json()
    assert len(data_madurai) == 1
    assert data_madurai[0]["username"] == "lmo_ramesh"

    # 3. Field LMO access should be forbidden (require_senior_lmo)
    res_forbidden = client.get("/api/v1/users/field-officers", headers=_auth_header(field1))
    assert res_forbidden.status_code == 403

def test_assign_ecommerce_task_and_fetch_assigned_to_me():
    db = TestingSessionLocal()
    senior = _make_user(db, "senior_priya", UserRole.SENIOR_LMO, district="Madurai")
    field_officer = _make_user(db, "lmo_ramesh", UserRole.FIELD_LMO, district="Madurai")
    other_officer = _make_user(db, "lmo_suresh", UserRole.FIELD_LMO, district="Coimbatore")

    # Create an e-commerce failed scan
    scan = Scan(
        scan_id=uuid.uuid4(),
        source=ScanSource.ECOMMERCE,
        image_url="/static/uploads/blinkit_chips.jpg",
        evidence_hash="evidence_hash_123",
        status=ScanStatus.FAILED,
        reviewer_note="Net quantity declaration completely missing on product face.",
        created_at=datetime.now(timezone.utc),
    )
    db.add(scan)
    db.commit()

    dim_field = ExtractedField(
        id=uuid.uuid4(),
        scan_id=scan.scan_id,
        field_name="declared_dimensions",
        raw_text="h:180mm w:120mm | platform:blinkit | qty:200g",
    )
    product_field = ExtractedField(
        id=uuid.uuid4(),
        scan_id=scan.scan_id,
        field_name="brand_name",
        raw_text="Bingo Mad Angles 200g",
    )
    rule_fail = RuleResult(
        id=uuid.uuid4(),
        scan_id=scan.scan_id,
        rule_id="6_1_e",
        status=RuleStatus.FAIL,
        reason="MRP declaration missing tax phrase",
    )
    db.add_all([dim_field, product_field, rule_fail])
    db.commit()

    # Step 1: Senior assigns scan to field_officer per §5.3
    assign_payload = {
        "scan_id": str(scan.scan_id),
        "assigned_to_lmo_id": str(field_officer.id),
        "task_type": "field_followup",
    }
    assign_res = client.post(
        "/api/v1/events/task-assigned",
        json=assign_payload,
        headers=_auth_header(senior),
    )
    assert assign_res.status_code == 200

    # Verify database scan assignment
    db.expire_all()
    db_scan = db.query(Scan).filter(Scan.scan_id == scan.scan_id).first()
    assert db_scan.assigned_lmo_id == field_officer.id

    # Verify event log emitted
    event_entry = db.query(EventLog).filter(EventLog.event_type == "task.assigned").first()
    assert event_entry is not None
    assert event_entry.payload["scan_id"] == str(scan.scan_id)
    assert event_entry.payload["assigned_to_lmo_id"] == str(field_officer.id)
    assert event_entry.payload["task_type"] == "field_followup"

    # Step 2: Assigned field officer retrieves their task via GET /scans/assigned-to-me
    res_tasks = client.get("/api/v1/scans/assigned-to-me", headers=_auth_header(field_officer))
    assert res_tasks.status_code == 200
    tasks = res_tasks.json()
    assert len(tasks) == 1
    task = tasks[0]
    assert task["scan_id"] == str(scan.scan_id)
    assert task["source"] == "ecommerce"
    assert task["status"] == "FAILED"
    assert task["product_name"] == "Bingo Mad Angles 200g"
    assert task["platform"] == "blinkit"
    assert task["task_type"] == "field_followup"
    assert "Net quantity declaration completely missing" in task["instructions"]
    assert any("6_1_e" in v for v in task["rule_violations"])

    # Step 3: Other field officer sees empty assigned tasks list
    res_other = client.get("/api/v1/scans/assigned-to-me", headers=_auth_header(other_officer))
    assert res_other.status_code == 200
    assert len(res_other.json()) == 0
