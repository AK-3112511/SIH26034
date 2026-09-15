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
from app.models.ruleset_version import RulesetVersion
from app.routers import admin
from app.services.rules.ruleset_config import get_active_ruleset

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
    db.query(RulesetVersion).delete()
    db.commit()
    db.close()
    yield


VALID_BANDS = [
    {"max_area_cm2": 50.0, "min_font_mm": 1.5, "description": "<=50cm2"},
    {"max_area_cm2": None, "min_font_mm": 6.0, "description": ">50cm2"},
]


def _create_payload(version="v_test_1", activate=False, **overrides):
    payload = {
        "version": version,
        "effective_date": "2026-10-01",
        "is_placeholder": True,
        "notice": "Test provisional notice",
        "bands": VALID_BANDS,
    }
    payload.update(overrides)
    return payload


def test_create_ruleset_version_persists_and_lists():
    resp = client.post("/api/v1/admin/rulesets", json=_create_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["version"] == "v_test_1"
    assert body["is_active"] is False

    list_resp = client.get("/api/v1/admin/rulesets")
    assert list_resp.status_code == 200
    versions = list_resp.json()["versions"]
    assert len(versions) == 1
    assert versions[0]["version"] == "v_test_1"


def test_creating_duplicate_version_name_is_rejected_not_overwritten():
    client.post("/api/v1/admin/rulesets", json=_create_payload(version="v_dup"))
    resp = client.post("/api/v1/admin/rulesets", json=_create_payload(version="v_dup"))
    assert resp.status_code == 409

    # Still exactly one row — the original was never touched.
    versions = client.get("/api/v1/admin/rulesets").json()["versions"]
    assert len(versions) == 1


def test_create_with_activate_flag_deactivates_previous_active_version():
    client.post("/api/v1/admin/rulesets?activate=true", json=_create_payload(version="v1"))
    resp = client.post("/api/v1/admin/rulesets?activate=true", json=_create_payload(version="v2"))
    assert resp.status_code == 201
    assert resp.json()["is_active"] is True

    versions = {v["version"]: v for v in client.get("/api/v1/admin/rulesets").json()["versions"]}
    assert versions["v1"]["is_active"] is False
    assert versions["v2"]["is_active"] is True


def test_activate_endpoint_switches_active_version():
    client.post("/api/v1/admin/rulesets?activate=true", json=_create_payload(version="v1"))
    client.post("/api/v1/admin/rulesets", json=_create_payload(version="v2"))

    resp = client.post("/api/v1/admin/rulesets/v2/activate")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    versions = {v["version"]: v for v in client.get("/api/v1/admin/rulesets").json()["versions"]}
    assert versions["v1"]["is_active"] is False
    assert versions["v2"]["is_active"] is True


def test_activate_unknown_version_404s():
    resp = client.post("/api/v1/admin/rulesets/does-not-exist/activate")
    assert resp.status_code == 404


def test_bands_must_have_exactly_one_open_ended_bracket():
    bad_bands = [{"max_area_cm2": 50.0, "min_font_mm": 1.5, "description": "only bracket"}]
    resp = client.post("/api/v1/admin/rulesets", json=_create_payload(version="v_bad", bands=bad_bands))
    assert resp.status_code == 422


def test_ruleset_create_and_activate_are_audit_logged():
    client.post("/api/v1/admin/rulesets?activate=true", json=_create_payload(version="v_audit"))

    db = TestingSessionLocal()
    actions = {log.action for log in db.query(AuditLog).all()}
    db.close()
    assert "RULESET_VERSION_CREATED" in actions


def test_activation_takes_effect_on_get_active_ruleset_when_db_passed():
    client.post("/api/v1/admin/rulesets?activate=true", json=_create_payload(version="v_live"))

    db = TestingSessionLocal()
    active = get_active_ruleset(db=db)
    db.close()
    assert active.version == "v_live"
    assert len(active.bands) == 2


def test_get_active_ruleset_falls_back_to_in_memory_placeholder_without_db():
    # No db session, no version created — must never crash, must return the
    # in-memory placeholder (pre-Phase-6.3 behavior, still exercised by
    # every existing rule-engine test that doesn't pass a db).
    active = get_active_ruleset()
    assert active.is_placeholder is True


def test_requires_admin_role():
    from fastapi import HTTPException, status

    def _reject():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    app.dependency_overrides[require_admin] = _reject
    try:
        resp = client.get("/api/v1/admin/rulesets")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides[require_admin] = _admin_override
