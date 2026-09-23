import io
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from geoalchemy2 import Geometry
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user, get_db
from app.db.base import Base
from app.main import app
from app.models.enums import ScanSource, ScanStatus, UserRole
from app.models.rule_result import RuleResult
from app.models.scan import Scan
from app.models.user import User


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
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

from sqlalchemy import event

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

@pytest.fixture(scope="function")
def test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def test_generate_challan_success(test_db: Session):
    # Setup test user
    test_user_id = uuid.uuid4()
    test_user = User(
        id=test_user_id,
        username="lmo_test",
        email="lmo@test.com",
        hashed_password="fake",
        role=UserRole.SENIOR_LMO,
        is_active=True,
        full_name="LMO Officer",
        district="Bangalore",
    )
    test_db.add(test_user)
    
    # Generate dummy image bytes (needs to be a valid image for PIL)
    from PIL import Image as PILImage
    img = PILImage.new('RGB', (100, 100), color='white')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    dummy_img = img_byte_arr.getvalue()
    
    # Store dummy image in storage directly since we bypass ingest
    from app.services.storage import get_storage_provider
    storage = get_storage_provider()
    image_url = storage.upload_file(dummy_img, "test.jpg")
    
    # Setup scan
    scan_id = uuid.uuid4()
    scan = Scan(
        scan_id=scan_id,
        source=ScanSource.MOBILE,
        status=ScanStatus.FAILED,
        image_url=image_url,
        evidence_hash="dummy_hash",
        lat=12.97,
        lng=77.59,
        captured_at_utc=datetime.now(timezone.utc),
        assigned_lmo_id=test_user_id
    )
    test_db.add(scan)
    
    # Setup extracted fields and rules
    rule = RuleResult(
        id=uuid.uuid4(),
        scan_id=scan_id,
        rule_id="RULE_01",
        status="FAIL",
        reason="MRP missing"
    )
    test_db.add(rule)
    
    test_db.commit()
    
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db] = lambda: test_db
    
    try:
        response = client.post(
            "/api/v1/challans/generate",
            json={"scan_id": str(scan_id)}
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert "challan_id" in data
        assert data["pdf_url"] is not None
        assert data["pdf_hash"] is not None
        
        # Ensure it works when fetching PDF
        pdf_bytes = storage.get_file(data["pdf_url"])
        assert len(pdf_bytes) > 0
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

def test_generate_challan_missing_gps(test_db: Session):
    # Setup test user
    test_user_id = uuid.uuid4()
    test_user = User(
        id=test_user_id, 
        username="lmo2",
        email="lmo2@test.com", 
        hashed_password="fake",
        full_name="L2",
        role=UserRole.SENIOR_LMO, 
        is_active=True
    )
    test_db.add(test_user)
    
    scan_id = uuid.uuid4()
    scan = Scan(
        scan_id=scan_id,
        source=ScanSource.MOBILE,  # field capture: GPS is mandatory
        status=ScanStatus.FAILED,
        image_url="/static/fake.jpg",
        evidence_hash="hash",
        lat=None, # Missing GPS
        lng=None
    )
    test_db.add(scan)
    rule = RuleResult(id=uuid.uuid4(), scan_id=scan_id, rule_id="R1", status="FAIL", reason="fail")
    test_db.add(rule)
    test_db.commit()
    
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db] = lambda: test_db
    
    try:
        response = client.post("/api/v1/challans/generate", json={"scan_id": str(scan_id)})
        assert response.status_code == 400
        assert "GPS coordinates are missing" in response.text
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

def test_list_challans(test_db: Session):
    test_user = User(
        id=uuid.uuid4(), 
        username="lmo3",
        email="lmo3@test.com", 
        hashed_password="fake",
        full_name="L3",
        role=UserRole.SENIOR_LMO, 
        is_active=True
    )
    test_db.add(test_user)
    
    # Add dummy challan
    from datetime import datetime, timezone

    from app.models.challan import Challan
    ch = Challan(
        challan_id=uuid.uuid4(),
        scan_id=uuid.uuid4(),
        lmo_id=test_user.id,
        pdf_url="/static/fake.pdf",
        pdf_hash="fakehash",
        generated_at=datetime.now(timezone.utc)
    )
    test_db.add(ch)
    test_db.commit()
    
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db] = lambda: test_db
    
    try:
        response = client.get("/api/v1/challans/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        # Stored keys are rendered as signed, time-limited download URLs.
        assert data["items"][0]["pdf_url"].startswith("/api/v1/files/fake.pdf?exp=")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_list_challans_filtered_by_scan(test_db: Session):
    """The scan detail screen must be able to ask whether a notice exists.

    Without this filter the only way to find out was to POST to /generate,
    which is a request to issue one.
    """
    from datetime import datetime, timezone

    from app.models.challan import Challan

    test_user = User(
        id=uuid.uuid4(),
        username="lmo4",
        email="lmo4@test.com",
        hashed_password="fake",
        full_name="L4",
        role=UserRole.SENIOR_LMO,
        is_active=True,
    )
    test_db.add(test_user)

    wanted_scan_id = uuid.uuid4()
    for scan_id in (wanted_scan_id, uuid.uuid4(), uuid.uuid4()):
        test_db.add(
            Challan(
                challan_id=uuid.uuid4(),
                scan_id=scan_id,
                lmo_id=test_user.id,
                pdf_url="/static/fake.pdf",
                pdf_hash="fakehash",
                generated_at=datetime.now(timezone.utc),
            )
        )
    test_db.commit()

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db] = lambda: test_db

    try:
        response = client.get("/api/v1/challans/", params={"scan_id": str(wanted_scan_id)})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["scan_id"] == str(wanted_scan_id)

        # A scan with no notice returns an empty page, not a 404.
        empty = client.get("/api/v1/challans/", params={"scan_id": str(uuid.uuid4())})
        assert empty.status_code == 200
        assert empty.json()["total"] == 0
        assert empty.json()["items"] == []
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
