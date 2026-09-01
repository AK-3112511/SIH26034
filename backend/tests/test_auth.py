import os
import sys
import uuid
import pytest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
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
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.models.audit_log import AuditLog
from app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token
from app.core.deps import get_current_user, require_roles, require_field_lmo, require_senior_lmo, require_admin
from app.routers import auth

# In-memory SQLite database for testing auth services
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables for testing (users, audit_logs)
User.__table__.create(bind=engine, checkfirst=True)
AuditLog.__table__.create(bind=engine, checkfirst=True)

# Build test FastAPI app
app = FastAPI()
app.include_router(auth.router, prefix="/api/v1")

# Add test routes with role guards
@app.get("/test/field-only")
def field_only_route(user: User = Depends(require_field_lmo)):
    return {"message": "field_lmo ok", "user_id": str(user.id)}

@app.get("/test/senior-only")
def senior_only_route(user: User = Depends(require_senior_lmo)):
    return {"message": "senior_lmo ok", "user_id": str(user.id)}

@app.get("/test/admin-only")
def admin_only_route(user: User = Depends(require_admin)):
    return {"message": "admin ok", "user_id": str(user.id)}

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


def test_password_hashing():
    raw_pass = "LegalMetrology@2026"
    hashed = get_password_hash(raw_pass)
    assert hashed != raw_pass
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_payload_claims():
    lmo_id = str(uuid.uuid4())
    token = create_access_token(
        lmo_id=lmo_id,
        role=UserRole.FIELD_LMO.value,
        district="Chennai Central"
    )
    payload = decode_access_token(token)
    assert payload["sub"] == lmo_id
    assert payload["lmo_id"] == lmo_id
    assert payload["role"] == "field_lmo"
    assert payload["district"] == "Chennai Central"
    assert "exp" in payload
    assert "iat" in payload


def test_login_and_audit_logging_success():
    db = TestingSessionLocal()
    user_id = uuid.uuid4()
    test_user = User(
        id=user_id,
        username="lmo_ramesh",
        email="ramesh@legalmetrology.gov.in",
        hashed_password=get_password_hash("Inspect#2026"),
        full_name="Ramesh Kumar",
        role=UserRole.FIELD_LMO,
        district="Coimbatore",
        is_active=True
    )
    db.add(test_user)
    db.commit()
    db.close()

    # Login with username
    response = client.post("/api/v1/auth/login", json={
        "username": "lmo_ramesh",
        "password": "Inspect#2026"
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["id"] == str(user_id)
    assert data["user"]["role"] == "field_lmo"
    assert data["user"]["district"] == "Coimbatore"

    # Verify audit log entry
    db = TestingSessionLocal()
    audit = db.query(AuditLog).filter(AuditLog.action == "USER_LOGIN_SUCCESS").first()
    assert audit is not None
    assert audit.actor_id == user_id
    assert audit.target_type == "user"
    assert audit.target_id == str(user_id)
    assert audit.detail["role"] == "field_lmo"
    assert audit.detail["district"] == "Coimbatore"
    db.close()


def test_login_with_email():
    db = TestingSessionLocal()
    user_id = uuid.uuid4()
    test_user = User(
        id=user_id,
        username="senior_priya",
        email="priya@legalmetrology.gov.in",
        hashed_password=get_password_hash("SeniorPass@123"),
        full_name="Priya Sharma",
        role=UserRole.SENIOR_LMO,
        district="Madurai",
        is_active=True
    )
    db.add(test_user)
    db.commit()
    db.close()

    # Login using email instead of username
    response = client.post("/api/v1/auth/login", json={
        "username": "priya@legalmetrology.gov.in",
        "password": "SeniorPass@123"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["role"] == "senior_lmo"
    assert data["user"]["district"] == "Madurai"


def test_login_failed_and_audit_logging():
    db = TestingSessionLocal()
    user_id = uuid.uuid4()
    test_user = User(
        id=user_id,
        username="admin_user",
        email="admin@legalmetrology.gov.in",
        hashed_password=get_password_hash("AdminPass#1"),
        full_name="National Admin",
        role=UserRole.ADMIN,
        district="New Delhi",
        is_active=True
    )
    db.add(test_user)
    db.commit()
    db.close()

    # Attempt with wrong password
    response = client.post("/api/v1/auth/login", json={
        "username": "admin_user",
        "password": "WrongPassword!"
    })
    assert response.status_code == 401
    assert "Incorrect username/email or password" in response.json()["detail"]

    # Verify audit log recorded failure
    db = TestingSessionLocal()
    audit = db.query(AuditLog).filter(AuditLog.action == "USER_LOGIN_FAILED").first()
    assert audit is not None
    assert audit.target_type == "user"
    assert audit.detail["attempted_identifier"] == "admin_user"
    assert audit.detail["reason"] == "Invalid credentials"
    db.close()


def test_auth_me_roundtrip():
    db = TestingSessionLocal()
    user_id = uuid.uuid4()
    test_user = User(
        id=user_id,
        username="lmo_test",
        email="test@legalmetrology.gov.in",
        hashed_password=get_password_hash("Pass123!"),
        full_name="Test Officer",
        role=UserRole.FIELD_LMO,
        district="Salem",
        is_active=True
    )
    db.add(test_user)
    db.commit()
    db.close()

    # Login to get token
    login_resp = client.post("/api/v1/auth/login", json={
        "username": "lmo_test",
        "password": "Pass123!"
    })
    token = login_resp.json()["access_token"]

    # Call /auth/me with Bearer token
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["id"] == str(user_id)
    assert me_data["username"] == "lmo_test"
    assert me_data["email"] == "test@legalmetrology.gov.in"
    assert me_data["role"] == "field_lmo"
    assert me_data["district"] == "Salem"


def test_role_guards_enforcement():
    db = TestingSessionLocal()
    field_id = uuid.uuid4()
    senior_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    db.add_all([
        User(
            id=field_id,
            username="guard_field",
            email="field@gov.in",
            hashed_password=get_password_hash("pass"),
            full_name="Field Officer",
            role=UserRole.FIELD_LMO,
            district="Chennai",
            is_active=True
        ),
        User(
            id=senior_id,
            username="guard_senior",
            email="senior@gov.in",
            hashed_password=get_password_hash("pass"),
            full_name="Senior Officer",
            role=UserRole.SENIOR_LMO,
            district="Chennai",
            is_active=True
        ),
        User(
            id=admin_id,
            username="guard_admin",
            email="admin@gov.in",
            hashed_password=get_password_hash("pass"),
            full_name="Admin Officer",
            role=UserRole.ADMIN,
            district="Delhi",
            is_active=True
        ),
    ])
    db.commit()
    db.close()

    field_token = create_access_token(str(field_id), UserRole.FIELD_LMO.value, "Chennai")
    senior_token = create_access_token(str(senior_id), UserRole.SENIOR_LMO.value, "Chennai")
    admin_token = create_access_token(str(admin_id), UserRole.ADMIN.value, "Delhi")

    # 1. Field LMO route
    r1 = client.get("/test/field-only", headers={"Authorization": f"Bearer {field_token}"})
    assert r1.status_code == 200
    r2 = client.get("/test/field-only", headers={"Authorization": f"Bearer {senior_token}"})
    assert r2.status_code == 403  # senior_lmo cannot access field_lmo only

    # 2. Senior LMO route (allows senior_lmo and admin)
    r3 = client.get("/test/senior-only", headers={"Authorization": f"Bearer {field_token}"})
    assert r3.status_code == 403  # field_lmo cannot access senior_lmo route
    r4 = client.get("/test/senior-only", headers={"Authorization": f"Bearer {senior_token}"})
    assert r4.status_code == 200
    r5 = client.get("/test/senior-only", headers={"Authorization": f"Bearer {admin_token}"})
    assert r5.status_code == 200

    # 3. Admin only route
    r6 = client.get("/test/admin-only", headers={"Authorization": f"Bearer {field_token}"})
    assert r6.status_code == 403
    r7 = client.get("/test/admin-only", headers={"Authorization": f"Bearer {senior_token}"})
    assert r7.status_code == 403
    r8 = client.get("/test/admin-only", headers={"Authorization": f"Bearer {admin_token}"})
    assert r8.status_code == 200


if __name__ == "__main__":
    pytest.main(["-v", __file__])
