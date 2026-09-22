"""Phase 7.1: Tests for real-time polling update layer per §6.2.

Tests:
1. scan.status_changed event emission with exact §6.2 payload shape
2. task.assigned event emission with exact §6.2 payload shape
3. /events/poll endpoint filtering by user, district, role, and 'since' timestamp
4. 7-day retention cutoff and pruning cleanup
5. Review submission triggers scan.status_changed event
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

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


# Compiles overrides for SQLite in-memory testing
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
from app.db.session import get_db, set_session_factory
from app.models.enums import ScanSource, ScanStatus, UserRole
from app.models.event import EventLog
from app.models.scan import Scan
from app.models.user import User
from app.routers import auth, events, scans
from app.services.events import (
    cleanup_expired_events,
    emit_scan_status_changed,
    emit_task_assigned,
)

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
set_session_factory(TestingSessionLocal)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    app = FastAPI()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(events.router, prefix="/api/v1")
    app.include_router(scans.router, prefix="/api/v1")

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def field_officer(db_session):
    user = User(
        id=uuid.uuid4(),
        username="field_officer_1",
        email="field1@tn.gov.in",
        hashed_password=get_password_hash("password123"),
        full_name="Thiru Field LMO",
        role=UserRole.FIELD_LMO,
        district="Chennai",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def senior_officer(db_session):
    user = User(
        id=uuid.uuid4(),
        username="senior_officer_1",
        email="senior1@tn.gov.in",
        hashed_password=get_password_hash("password123"),
        full_name="Dr. Senior LMO",
        role=UserRole.SENIOR_LMO,
        district="Chennai",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    user = User(
        id=uuid.uuid4(),
        username="admin_officer",
        email="admin@tn.gov.in",
        hashed_password=get_password_hash("password123"),
        full_name="State Metrology Controller",
        role=UserRole.ADMIN,
        district=None,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        lmo_id=str(user.id),
        role=user.role.value,
        district=user.district,
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Event Emission & Payload Shape Tests (Strictly per §6.2)
# ---------------------------------------------------------------------------

def test_emit_scan_status_changed_payload_shape(db_session, field_officer):
    """Verify scan.status_changed payload matches §6.2:
    payload: { scan_id, new_status, rule_results[], assigned_lmo_id }
    """
    scan_id = uuid.uuid4()
    rule_results = [
        {"rule_id": "6_1_a", "status": "PASS", "reason": "Manufacturer details verified"},
        {"rule_id": "6_1_e", "status": "FAIL", "reason": "Missing tax phrase"},
    ]

    event = emit_scan_status_changed(
        db=db_session,
        scan_id=scan_id,
        new_status="FAILED",
        rule_results=rule_results,
        assigned_lmo_id=field_officer.id,
        district="Chennai",
    )

    assert event.event_type == "scan.status_changed"
    payload = event.payload
    assert payload["scan_id"] == str(scan_id)
    assert payload["new_status"] == "FAILED"
    assert payload["assigned_lmo_id"] == str(field_officer.id)
    assert len(payload["rule_results"]) == 2
    assert payload["rule_results"][0]["rule_id"] == "6_1_a"
    assert payload["rule_results"][1]["status"] == "FAIL"


def test_emit_task_assigned_payload_shape(db_session, field_officer):
    """Verify task.assigned payload matches §6.2:
    payload: { scan_id, assigned_to_lmo_id, task_type: 'field_followup' }
    """
    scan_id = uuid.uuid4()
    event = emit_task_assigned(
        db=db_session,
        scan_id=scan_id,
        assigned_to_lmo_id=field_officer.id,
        task_type="field_followup",
    )

    assert event.event_type == "task.assigned"
    payload = event.payload
    assert payload["scan_id"] == str(scan_id)
    assert payload["assigned_to_lmo_id"] == str(field_officer.id)
    assert payload["task_type"] == "field_followup"


# ---------------------------------------------------------------------------
# 2. Polling Endpoint /events/poll Tests
# ---------------------------------------------------------------------------

def test_poll_events_for_field_officer(client, db_session, field_officer, senior_officer):
    """Field officer receives personal events (own scan status changes & assigned tasks)."""
    scan_1 = uuid.uuid4()
    scan_2 = uuid.uuid4()

    # Event 1: Assigned to this field officer
    emit_scan_status_changed(
        db=db_session,
        scan_id=scan_1,
        new_status="PASSED",
        rule_results=[],
        assigned_lmo_id=field_officer.id,
        district="Chennai",
    )

    # Event 2: Assigned to another officer (senior_officer) in Coimbatore
    emit_scan_status_changed(
        db=db_session,
        scan_id=scan_2,
        new_status="FAILED",
        rule_results=[],
        assigned_lmo_id=senior_officer.id,
        district="Coimbatore",
    )

    # Event 3: Task assigned to this field officer
    emit_task_assigned(
        db=db_session,
        scan_id=scan_2,
        assigned_to_lmo_id=field_officer.id,
    )

    headers = auth_headers(field_officer)
    response = client.get("/api/v1/events/poll", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["count"] == 2
    event_types = [e["event_type"] for e in data["events"]]
    assert "scan.status_changed" in event_types
    assert "task.assigned" in event_types


def test_poll_events_district_routing_for_senior_officer(client, db_session, field_officer, senior_officer):
    """Senior LMO in Chennai receives all queue updates for Chennai district."""
    scan_chennai = uuid.uuid4()
    scan_salem = uuid.uuid4()

    # Chennai scan status changed -> should be visible to senior_officer (Chennai)
    emit_scan_status_changed(
        db=db_session,
        scan_id=scan_chennai,
        new_status="PENDING_REVIEW",
        rule_results=[],
        assigned_lmo_id=field_officer.id,
        district="Chennai",
    )

    # Salem scan status changed -> NOT visible to Chennai senior_officer
    emit_scan_status_changed(
        db=db_session,
        scan_id=scan_salem,
        new_status="PENDING_REVIEW",
        rule_results=[],
        assigned_lmo_id=None,
        district="Salem",
    )

    headers = auth_headers(senior_officer)
    response = client.get("/api/v1/events/poll", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["count"] == 1
    assert data["events"][0]["payload"]["scan_id"] == str(scan_chennai)


def test_poll_events_since_filter(client, db_session, field_officer):
    """Using 'since' timestamp returns only newer events."""
    now = datetime.now(timezone.utc)
    past_time = now - timedelta(minutes=10)

    # Old event
    old_event = EventLog(
        id=uuid.uuid4(),
        event_type="scan.status_changed",
        payload={"scan_id": str(uuid.uuid4()), "new_status": "PASSED"},
        target_user_id=field_officer.id,
        created_at=past_time,
    )
    db_session.add(old_event)

    # Recent event
    recent_scan_id = uuid.uuid4()
    emit_scan_status_changed(
        db=db_session,
        scan_id=recent_scan_id,
        new_status="FAILED",
        assigned_lmo_id=field_officer.id,
        district="Chennai",
    )

    headers = auth_headers(field_officer)
    cutoff = (now - timedelta(minutes=2)).isoformat()
    response = client.get(f"/api/v1/events/poll?since={cutoff}", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["count"] == 1
    assert data["events"][0]["payload"]["scan_id"] == str(recent_scan_id)


# ---------------------------------------------------------------------------
# 3. Retention Policy & Cleanup Tests (7-day window)
# ---------------------------------------------------------------------------

def test_cleanup_expired_events_retention(db_session, field_officer):
    """Events older than 7 days are pruned; newer events remain."""
    now = datetime.now(timezone.utc)

    # Event 1: 10 days old (expired)
    expired_event = EventLog(
        id=uuid.uuid4(),
        event_type="scan.status_changed",
        payload={"scan_id": "old_scan"},
        target_user_id=field_officer.id,
        created_at=now - timedelta(days=10),
    )
    # Event 2: 3 days old (valid)
    valid_event = EventLog(
        id=uuid.uuid4(),
        event_type="scan.status_changed",
        payload={"scan_id": "recent_scan"},
        target_user_id=field_officer.id,
        created_at=now - timedelta(days=3),
    )
    db_session.add_all([expired_event, valid_event])
    db_session.commit()

    deleted = cleanup_expired_events(db=db_session, retention_days=7)
    assert deleted == 1

    remaining = db_session.query(EventLog).all()
    assert len(remaining) == 1
    assert remaining[0].payload["scan_id"] == "recent_scan"


def test_admin_prune_endpoint(client, db_session, admin_user, field_officer):
    """Admin can trigger manual retention pruning via POST /api/v1/events/prune."""
    now = datetime.now(timezone.utc)
    expired = EventLog(
        id=uuid.uuid4(),
        event_type="scan.status_changed",
        payload={"scan_id": "expired"},
        target_user_id=field_officer.id,
        created_at=now - timedelta(days=15),
    )
    db_session.add(expired)
    db_session.commit()

    headers = auth_headers(admin_user)
    response = client.post("/api/v1/events/prune?retention_days=7", headers=headers)
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 1


# ---------------------------------------------------------------------------
# 4. Task Assignment Flow Test (§5.3 & §6.2)
# ---------------------------------------------------------------------------

def test_assign_scan_task_endpoint(client, db_session, senior_officer, field_officer):
    """Senior LMO assigns e-commerce or review scan to field LMO -> emits task.assigned."""
    scan = Scan(
        scan_id=uuid.uuid4(),
        source=ScanSource.ECOMMERCE,
        image_url="http://test/img.jpg",
        evidence_hash="sha256:123",
        status=ScanStatus.FAILED,
    )
    db_session.add(scan)
    db_session.commit()

    headers = auth_headers(senior_officer)
    payload = {
        "scan_id": str(scan.scan_id),
        "assigned_to_lmo_id": str(field_officer.id),
        "task_type": "field_followup",
    }
    response = client.post("/api/v1/events/task-assigned", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["task_type"] == "field_followup"

    # Verify event was persisted
    events_in_db = db_session.query(EventLog).filter(EventLog.event_type == "task.assigned").all()
    assert len(events_in_db) == 1
    assert events_in_db[0].payload["assigned_to_lmo_id"] == str(field_officer.id)


def test_review_submit_emits_scan_status_changed(client, db_session, senior_officer, field_officer):
    """Submitting a review decision emits scan.status_changed per §5.2 & §6.2."""
    scan = Scan(
        scan_id=uuid.uuid4(),
        source=ScanSource.MOBILE,
        image_url="http://test/mobile.jpg",
        evidence_hash="sha256:456",
        status=ScanStatus.PENDING_REVIEW,
        assigned_lmo_id=field_officer.id,
    )
    db_session.add(scan)
    db_session.commit()

    headers = auth_headers(senior_officer)
    review_payload = {
        "decision": "PASSED",
        "reviewer_note": "Confirmed compliance under Rule 6(1)(a) with valid label declarations.",
    }
    response = client.post(f"/api/v1/scans/{scan.scan_id}/review", json=review_payload, headers=headers)
    assert response.status_code == 200

    events_in_db = db_session.query(EventLog).filter(EventLog.event_type == "scan.status_changed").all()
    assert len(events_in_db) == 1
    event = events_in_db[0]
    assert event.payload["scan_id"] == str(scan.scan_id)
    assert event.payload["new_status"] == "PASSED"
    assert event.payload["assigned_lmo_id"] == str(field_officer.id)

