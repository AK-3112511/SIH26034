import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
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

from app.core.security import decode_access_token, get_password_hash
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from app.models.user import User
from app.routers import auth

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

User.__table__.create(bind=engine, checkfirst=True)
AuditLog.__table__.create(bind=engine, checkfirst=True)

app = FastAPI()
app.include_router(auth.router, prefix="/api/v1")

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
    db.query(User).delete()
    db.commit()
    db.close()


def test_dashboard_login_senior_lmo_granted():
    """Confirm a senior_lmo token is issued and has valid role for dashboard access."""
    db = TestingSessionLocal()
    user_id = uuid.uuid4()
    senior_user = User(
        id=user_id,
        username="senior_priya",
        email="priya@legalmetrology.gov.in",
        hashed_password=get_password_hash("SeniorSecret#1"),
        full_name="Priya Sharma",
        role=UserRole.SENIOR_LMO,
        district="Madurai",
        is_active=True
    )
    db.add(senior_user)
    db.commit()
    db.close()

    resp = client.post("/api/v1/auth/login", json={
        "username": "senior_priya",
        "password": "SeniorSecret#1"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["role"] == "senior_lmo"

    # Verify token payload
    token = data["access_token"]
    payload = decode_access_token(token)
    assert payload["role"] == "senior_lmo"
    assert payload["district"] == "Madurai"
    
    # Web dashboard access condition
    is_dashboard_allowed = payload["role"] in ["senior_lmo", "admin"]
    assert is_dashboard_allowed is True


def test_dashboard_login_admin_granted():
    """Confirm an admin token is issued and has valid role for dashboard access."""
    db = TestingSessionLocal()
    user_id = uuid.uuid4()
    admin_user = User(
        id=user_id,
        username="admin_rajesh",
        email="rajesh@legalmetrology.gov.in",
        hashed_password=get_password_hash("AdminSecret#1"),
        full_name="Rajesh V",
        role=UserRole.ADMIN,
        district="Chennai Central",
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    db.close()

    resp = client.post("/api/v1/auth/login", json={
        "username": "admin_rajesh",
        "password": "AdminSecret#1"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["role"] == "admin"

    token = data["access_token"]
    payload = decode_access_token(token)
    assert payload["role"] == "admin"

    # Web dashboard access condition
    is_dashboard_allowed = payload["role"] in ["senior_lmo", "admin"]
    assert is_dashboard_allowed is True


def test_dashboard_login_field_lmo_rejected():
    """Confirm a field_lmo token is issued by auth service but rejected for dashboard access."""
    db = TestingSessionLocal()
    user_id = uuid.uuid4()
    field_user = User(
        id=user_id,
        username="lmo_ramesh",
        email="ramesh@legalmetrology.gov.in",
        hashed_password=get_password_hash("FieldSecret#1"),
        full_name="Ramesh Kumar",
        role=UserRole.FIELD_LMO,
        district="Coimbatore",
        is_active=True
    )
    db.add(field_user)
    db.commit()
    db.close()

    resp = client.post("/api/v1/auth/login", json={
        "username": "lmo_ramesh",
        "password": "FieldSecret#1"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["role"] == "field_lmo"

    token = data["access_token"]
    payload = decode_access_token(token)
    assert payload["role"] == "field_lmo"

    # Web dashboard access rule: field_lmo is rejected
    is_dashboard_allowed = payload["role"] in ["senior_lmo", "admin"]
    assert is_dashboard_allowed is False
