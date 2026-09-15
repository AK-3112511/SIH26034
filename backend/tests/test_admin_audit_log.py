import os
import sys
import uuid

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

from app.core.deps import require_admin
from app.db.base import Base
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from app.models.user import User
from app.routers import admin
from app.services.audit import log_audit

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
app.include_router(admin.router, prefix="/api/v1")


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


def _admin_override():
    return _FakeUser(UserRole.ADMIN)


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[require_admin] = _admin_override
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    db = TestingSessionLocal()
    db.query(AuditLog).delete()
    db.query(User).delete()
    db.commit()
    db.close()
    yield


def test_audit_log_lists_entries_newest_first():
    db = TestingSessionLocal()
    actor = User(
        id=uuid.uuid4(), username="admin_1", email="a1@x.com", hashed_password="x",
        full_name="Admin One", role=UserRole.ADMIN, is_active=True,
    )
    db.add(actor)
    db.commit()

    log_audit(db, action="SCAN_INGESTED", target_type="scan", target_id="s1", actor_id=actor.id)
    log_audit(db, action="USER_CREATED", target_type="user", target_id="u1", actor_id=actor.id)
    db.commit()
    db.close()

    resp = client.get("/api/v1/admin/audit-log")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    # Newest first.
    assert data["items"][0]["action"] == "USER_CREATED"
    assert data["items"][0]["actor_username"] == "admin_1"


def test_audit_log_filters_by_target_type():
    db = TestingSessionLocal()
    log_audit(db, action="SCAN_INGESTED", target_type="scan", target_id="s1")
    log_audit(db, action="RULESET_VERSION_CREATED", target_type="ruleset", target_id="v1")
    db.commit()
    db.close()

    resp = client.get("/api/v1/admin/audit-log", params={"target_type": "ruleset"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["target_type"] == "ruleset"


def test_audit_log_filters_by_action():
    db = TestingSessionLocal()
    log_audit(db, action="SCAN_INGESTED", target_type="scan", target_id="s1")
    log_audit(db, action="SCAN_INGESTED", target_type="scan", target_id="s2")
    log_audit(db, action="USER_CREATED", target_type="user", target_id="u1")
    db.commit()
    db.close()

    resp = client.get("/api/v1/admin/audit-log", params={"action": "SCAN_INGESTED"})
    data = resp.json()
    assert data["total"] == 2


def test_audit_log_pagination():
    db = TestingSessionLocal()
    for i in range(5):
        log_audit(db, action="SCAN_INGESTED", target_type="scan", target_id=f"s{i}")
    db.commit()
    db.close()

    resp = client.get("/api/v1/admin/audit-log", params={"page": 1, "page_size": 2})
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2


def test_audit_log_actor_null_when_system_generated():
    db = TestingSessionLocal()
    log_audit(db, action="SCAN_INGESTED", target_type="scan", target_id="s1", actor_id=None)
    db.commit()
    db.close()

    resp = client.get("/api/v1/admin/audit-log")
    entry = resp.json()["items"][0]
    assert entry["actor_id"] is None
    assert entry["actor_username"] is None


def test_audit_log_detail_payload_preserved():
    db = TestingSessionLocal()
    log_audit(
        db, action="RULESET_VERSION_ACTIVATED", target_type="ruleset", target_id="v2",
        detail={"is_placeholder": True},
    )
    db.commit()
    db.close()

    resp = client.get("/api/v1/admin/audit-log")
    entry = resp.json()["items"][0]
    assert entry["detail"] == {"is_placeholder": True}


def test_audit_log_has_no_write_endpoints():
    """View-only by design — confirm no POST/PATCH/DELETE route exists on this path."""
    for method in ("post", "patch", "delete", "put"):
        resp = getattr(client, method)("/api/v1/admin/audit-log")
        assert resp.status_code in (404, 405)


def test_requires_admin_role():
    from fastapi import HTTPException, status

    def _reject():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    app.dependency_overrides[require_admin] = _reject
    try:
        resp = client.get("/api/v1/admin/audit-log")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides[require_admin] = _admin_override
