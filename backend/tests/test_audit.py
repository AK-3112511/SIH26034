import os
import sys
import uuid
import pytest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID, ENUM

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(ENUM, "sqlite")
def compile_enum_sqlite(type_, compiler, **kw):
    return "TEXT"

from app.db.base import Base
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.enums import UserRole
from app.services.audit import log_audit, log_status_change

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

User.__table__.create(bind=engine, checkfirst=True)
AuditLog.__table__.create(bind=engine, checkfirst=True)

@pytest.fixture(autouse=True)
def clean_db():
    db = TestingSessionLocal()
    db.query(AuditLog).delete()
    db.query(User).delete()
    db.commit()
    db.close()


def test_shared_log_audit_helper_exact_schema():
    db = TestingSessionLocal()
    actor_id = uuid.uuid4()
    target_id = str(uuid.uuid4())

    entry = log_audit(
        db=db,
        action="TEST_ACTION",
        target_type="scan",
        target_id=target_id,
        actor_id=actor_id,
        detail={"key": "value", "count": 42}
    )

    assert entry.id is not None
    assert entry.actor_id == actor_id
    assert entry.action == "TEST_ACTION"
    assert entry.target_type == "scan"
    assert entry.target_id == target_id
    assert entry.detail == {"key": "value", "count": 42}
    assert isinstance(entry.timestamp, datetime)

    # Verify directly from DB
    persisted = db.query(AuditLog).filter(AuditLog.id == entry.id).first()
    assert persisted is not None
    assert persisted.action == "TEST_ACTION"
    assert persisted.target_type == "scan"
    assert persisted.target_id == target_id
    assert persisted.detail["count"] == 42
    db.close()


def test_shared_log_status_change_helper():
    db = TestingSessionLocal()
    scan_id = str(uuid.uuid4())
    actor_id = uuid.uuid4()

    entry = log_status_change(
        db=db,
        target_type="scan",
        target_id=scan_id,
        new_status="PENDING_REVIEW",
        old_status="QUEUED",
        actor_id=actor_id,
        detail={"reason": "OCR confidence borderline (91%)"}
    )

    assert entry.action == "SCAN_STATUS_PENDING_REVIEW"
    assert entry.target_type == "scan"
    assert entry.target_id == scan_id
    assert entry.detail["old_status"] == "QUEUED"
    assert entry.detail["new_status"] == "PENDING_REVIEW"
    assert entry.detail["reason"] == "OCR confidence borderline (91%)"
    db.close()


def test_append_only_audit_log_records_multiple_events():
    db = TestingSessionLocal()
    actor_id = uuid.uuid4()
    target_id = str(uuid.uuid4())

    # Record 3 successive events
    log_audit(db, action="USER_LOGIN_SUCCESS", target_type="user", target_id=str(actor_id), actor_id=actor_id)
    log_audit(db, action="SCAN_INGESTED", target_type="scan", target_id=target_id, actor_id=actor_id)
    log_status_change(db, target_type="scan", target_id=target_id, new_status="PASSED", old_status="QUEUED", actor_id=actor_id)

    records = db.query(AuditLog).order_by(AuditLog.timestamp.asc()).all()
    assert len(records) == 3
    assert [r.action for r in records] == ["USER_LOGIN_SUCCESS", "SCAN_INGESTED", "SCAN_STATUS_PASSED"]
    assert [r.target_type for r in records] == ["user", "scan", "scan"]
    db.close()
