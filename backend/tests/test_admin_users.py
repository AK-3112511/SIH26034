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


def _create_payload(username="field_officer_1", **overrides):
    payload = {
        "username": username,
        "email": f"{username}@legalmetrology.gov.in",
        "password": "SuperSecret#1",
        "full_name": "Test Officer",
        "role": "field_lmo",
        "district": "Chennai",
    }
    payload.update(overrides)
    return payload


def test_create_user_persists_and_lists():
    resp = client.post("/api/v1/admin/users", json=_create_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "field_officer_1"
    assert body["role"] == "field_lmo"
    assert "password" not in body
    assert "hashed_password" not in body

    list_resp = client.get("/api/v1/admin/users")
    assert list_resp.status_code == 200
    users = list_resp.json()["users"]
    assert len(users) == 1


def test_create_user_rejects_duplicate_username_or_email():
    client.post("/api/v1/admin/users", json=_create_payload(username="dup_user"))
    resp = client.post("/api/v1/admin/users", json=_create_payload(username="dup_user"))
    assert resp.status_code == 409

    users = client.get("/api/v1/admin/users").json()["users"]
    assert len(users) == 1


def test_update_user_assigns_role_and_district():
    create_resp = client.post("/api/v1/admin/users", json=_create_payload(username="promote_me"))
    user_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"role": "senior_lmo", "district": "Madurai"},
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["role"] == "senior_lmo"
    assert body["district"] == "Madurai"


def test_update_user_can_deactivate_account():
    create_resp = client.post("/api/v1/admin/users", json=_create_payload(username="deactivate_me"))
    user_id = create_resp.json()["id"]

    patch_resp = client.patch(f"/api/v1/admin/users/{user_id}", json={"is_active": False})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_active"] is False


def test_update_unknown_user_404s():
    resp = client.patch(f"/api/v1/admin/users/{uuid.uuid4()}", json={"role": "admin"})
    assert resp.status_code == 404


def test_user_create_and_update_are_audit_logged():
    create_resp = client.post("/api/v1/admin/users", json=_create_payload(username="audited_user"))
    user_id = create_resp.json()["id"]
    client.patch(f"/api/v1/admin/users/{user_id}", json={"role": "senior_lmo"})

    db = TestingSessionLocal()
    actions = {log.action for log in db.query(AuditLog).all()}
    db.close()
    assert "USER_CREATED" in actions
    assert "USER_UPDATED" in actions


def test_requires_admin_role():
    from fastapi import HTTPException, status

    def _reject():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    app.dependency_overrides[require_admin] = _reject
    try:
        resp = client.get("/api/v1/admin/users")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides[require_admin] = _admin_override
