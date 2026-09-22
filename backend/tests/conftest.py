"""Shared test configuration.

The API suite runs against an in-memory SQLite database.  PostgreSQL-only
column types (JSONB, UUID, ENUM, PostGIS Geometry) are compiled to plain
SQLite types here once, instead of every test module carrying its own copy.
Tests that need a real PostGIS database are marked ``postgres`` and only run
when ``TEST_DATABASE_URL`` is set.
"""
from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Iterator

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Deterministic engines for the unit suite — never download models in CI.
os.environ.setdefault("OCR_ENGINE", "mock")
os.environ.setdefault("SEMANTIC_ENGINE", "rules")
os.environ.setdefault("DETECTOR_ENGINE", "geometric")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-characters-long")
os.environ.setdefault("SKIP_STARTUP_TASKS", "1")

import geoalchemy2.admin.dialects.sqlite
from geoalchemy2 import Geometry
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(ENUM, "sqlite")
def _compile_enum_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(Geometry, "sqlite")
def _compile_geometry_sqlite(type_, compiler, **kw):
    return "TEXT"


# Disable Spatialite-specific DDL callbacks for plain SQLite.
geoalchemy2.admin.dialects.sqlite.after_create = lambda *args, **kwargs: None
geoalchemy2.admin.dialects.sqlite.before_drop = lambda *args, **kwargs: None

_GEOM_FUNCS = ("AsEWKB", "AsBinary", "GeomFromEWKB", "GeomFromEWKT", "ST_GeomFromEWKT", "AsGeoJSON", "ST_AsEWKB")


def register_sqlite_geometry_functions(engine) -> None:
    """Register pass-through stand-ins for the PostGIS functions GeoAlchemy2 emits."""

    @event.listens_for(engine, "connect")
    def _connect(dbapi_connection, connection_record):
        for name in _GEOM_FUNCS:
            dbapi_connection.create_function(name, 1, lambda x: x)


def make_sqlite_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    register_sqlite_geometry_functions(engine)
    return engine


# ---------------------------------------------------------------------------
# Fixtures for new-style tests (the full app + a real user in the database)
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_engine():
    import app.models  # noqa: F401  — register every table
    from app.db.base import Base

    engine = make_sqlite_engine()
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Iterator[Session]:
    factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def app_client(db_engine, tmp_path, monkeypatch):
    """TestClient for the full application wired to the SQLite test database."""
    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.db.session import get_db, get_session_factory, set_session_factory
    from app.main import app

    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(tmp_path / "uploads"))
    factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    previous_factory = get_session_factory()
    set_session_factory(factory)

    def _override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        set_session_factory(previous_factory)


@pytest.fixture()
def make_user(db_session):
    """Create an active user of the given role and return it."""
    from app.core.security import get_password_hash
    from app.models.enums import UserRole
    from app.models.user import User

    def _make(role: UserRole = UserRole.FIELD_LMO, district: str = "Chennai", password: str = "Secret#123", **extra):
        suffix = uuid.uuid4().hex[:8]
        user = User(
            username=extra.get("username", f"{role.value}_{suffix}"),
            email=extra.get("email", f"{role.value}_{suffix}@example.gov.in"),
            hashed_password=get_password_hash(password),
            full_name=extra.get("full_name", f"Officer {suffix}"),
            role=role,
            district=district,
            is_active=extra.get("is_active", True),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        user.plain_password = password  # type: ignore[attr-defined]
        return user

    return _make


@pytest.fixture()
def auth_headers():
    from app.core.security import create_access_token

    def _headers(user) -> dict[str, str]:
        token = create_access_token(lmo_id=str(user.id), role=user.role.value, district=user.district)
        return {"Authorization": f"Bearer {token}"}

    return _headers


# Minimal valid JPEG bytes (a 1x1 image) for upload tests.
TINY_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f14"
    "1d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b080001000101011100"
    "ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc400b5100002010303020403050504040000"
    "017d01020300041105122131410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a"
    "3435363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a9293949596"
    "9798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2"
    "f3f4f5f6f7f8f9faffda0008010100003f00fbd0ffd9"
)


@pytest.fixture()
def tiny_jpeg() -> bytes:
    return TINY_JPEG


def pytest_configure(config):
    config.addinivalue_line("markers", "postgres: requires TEST_DATABASE_URL pointing at a PostGIS database")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("TEST_DATABASE_URL"):
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL not set")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip)
