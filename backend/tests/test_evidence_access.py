"""Phase A: authenticated ingestion, upload validation, signed evidence access, scoping."""
from __future__ import annotations

import io
import time
from datetime import datetime, timezone

from app.models.enums import UserRole
from app.services.files import sign_file_url, storage_key, verify_file_signature


def _ingest(client, headers, image_bytes, **extra):
    data = {
        "lat": "13.0827",
        "lng": "80.2707",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "device_id": "DEVICE-1",
        "reference_object_type": "debit_card",
        "auto_process": "false",
    }
    data.update(extra)
    return client.post(
        "/api/v1/scans/ingest",
        data=data,
        files={"image": ("capture.jpg", io.BytesIO(image_bytes), "image/jpeg")},
        headers=headers,
    )


def test_ingest_requires_authentication(app_client, tiny_jpeg):
    response = _ingest(app_client, {}, tiny_jpeg)
    assert response.status_code in (401, 403)


def test_ingest_records_capturing_officer(app_client, make_user, auth_headers, tiny_jpeg):
    officer = make_user(UserRole.FIELD_LMO)
    response = _ingest(app_client, auth_headers(officer), tiny_jpeg, product_name="  Parle-G 100g ")
    assert response.status_code == 201, response.text
    scan_id = response.json()["scan_id"]

    detail = app_client.get(f"/api/v1/scans/{scan_id}", headers=auth_headers(officer))
    assert detail.status_code == 200
    body = detail.json()
    assert body["captured_by_id"] == str(officer.id)
    assert body["product_name"] == "Parle-G 100g"
    assert body["reference_object_type"] == "debit_card"


def test_ingest_rejects_non_image_bytes(app_client, make_user, auth_headers):
    officer = make_user(UserRole.FIELD_LMO)
    response = _ingest(app_client, auth_headers(officer), b"this is not an image at all")
    assert response.status_code == 415


def test_ingest_rejects_oversized_upload(app_client, make_user, auth_headers, tiny_jpeg, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 64)
    officer = make_user(UserRole.FIELD_LMO)
    response = _ingest(app_client, auth_headers(officer), tiny_jpeg + b"\x00" * 200)
    assert response.status_code == 413


def test_field_officer_cannot_read_another_officers_scan(app_client, make_user, auth_headers, tiny_jpeg):
    owner = make_user(UserRole.FIELD_LMO)
    stranger = make_user(UserRole.FIELD_LMO)
    senior = make_user(UserRole.SENIOR_LMO)
    scan_id = _ingest(app_client, auth_headers(owner), tiny_jpeg).json()["scan_id"]

    assert app_client.get(f"/api/v1/scans/{scan_id}", headers=auth_headers(stranger)).status_code == 403
    assert app_client.get(f"/api/v1/scans/{scan_id}", headers=auth_headers(senior)).status_code == 200


def test_evidence_file_requires_signature_or_token(app_client, make_user, auth_headers, tiny_jpeg):
    officer = make_user(UserRole.FIELD_LMO)
    image_url = _ingest(app_client, auth_headers(officer), tiny_jpeg).json()["image_url"]
    assert image_url.startswith("/api/v1/files/")

    # Signed URL from the API works without headers (what <img> tags use).
    signed = app_client.get(image_url)
    assert signed.status_code == 200
    assert signed.headers["content-type"] == "image/jpeg"
    assert signed.content == tiny_jpeg

    # Bare key: no signature, no token -> refused.
    bare = image_url.split("?", 1)[0]
    assert app_client.get(bare).status_code == 401

    # Bare key with a bearer token -> allowed.
    assert app_client.get(bare, headers=auth_headers(officer)).status_code == 200

    # Tampered signature -> refused.
    tampered = image_url[:-4] + "0000"
    assert app_client.get(tampered).status_code == 401


def test_signature_expires():
    key = "abc_capture.jpg"
    url = sign_file_url(key, ttl_seconds=-1)
    query = dict(part.split("=") for part in url.split("?", 1)[1].split("&"))
    assert verify_file_signature(key, int(query["exp"]), query["sig"]) is False
    fresh = sign_file_url(key, ttl_seconds=60)
    query = dict(part.split("=") for part in fresh.split("?", 1)[1].split("&"))
    assert int(query["exp"]) > int(time.time())
    assert verify_file_signature(key, int(query["exp"]), query["sig"]) is True


def test_storage_key_normalises_legacy_and_signed_forms():
    assert storage_key("/static/uploads/x_y.jpg") == "x_y.jpg"
    assert storage_key("/api/v1/files/x_y.jpg?exp=1&sig=2") == "x_y.jpg"
    assert storage_key("../../etc/passwd") == "passwd"
    assert storage_key("https://bucket.s3.amazonaws.com/scans/x.jpg").startswith("https://")


def test_unknown_file_returns_404(app_client, make_user, auth_headers):
    officer = make_user(UserRole.FIELD_LMO)
    assert app_client.get("/api/v1/files/does_not_exist.jpg", headers=auth_headers(officer)).status_code == 404


def test_process_endpoints_require_senior_role(app_client, make_user, auth_headers, tiny_jpeg):
    officer = make_user(UserRole.FIELD_LMO)
    scan_id = _ingest(app_client, auth_headers(officer), tiny_jpeg).json()["scan_id"]
    assert app_client.post(f"/api/v1/scans/{scan_id}/process", headers=auth_headers(officer)).status_code == 403
    assert app_client.post("/api/v1/scans/process-queued", headers=auth_headers(officer)).status_code == 403


def test_ecommerce_ingest_hash_is_verifiable(app_client, make_user, auth_headers, tiny_jpeg):
    senior = make_user(UserRole.SENIOR_LMO)
    response = app_client.post(
        "/api/v1/scans/ingest-derived",
        data={
            "platform": "Blinkit",
            "package_height_mm": "120",
            "package_width_mm": "80",
            "product_name": "Bingo Mad Angles",
            "auto_process": "false",
        },
        files={"image": ("listing.png", io.BytesIO(tiny_jpeg), "image/png")},
        headers=auth_headers(senior),
    )
    assert response.status_code == 201, response.text
    scan_id = response.json()["scan_id"]
    verify = app_client.get(f"/api/v1/scans/{scan_id}/verify-hash", headers=auth_headers(senior))
    assert verify.status_code == 200
    assert verify.json()["is_valid"] is True
    detail = app_client.get(f"/api/v1/scans/{scan_id}", headers=auth_headers(senior)).json()
    assert detail["platform"] == "Blinkit"
    assert detail["product_name"] == "Bingo Mad Angles"
    assert detail["captured_by_id"] == str(senior.id)


def test_assignment_requires_active_field_officer(app_client, make_user, auth_headers, tiny_jpeg):
    senior = make_user(UserRole.SENIOR_LMO)
    other_senior = make_user(UserRole.SENIOR_LMO)
    inactive = make_user(UserRole.FIELD_LMO, is_active=False)
    field = make_user(UserRole.FIELD_LMO)
    scan_id = _ingest(app_client, auth_headers(field), tiny_jpeg).json()["scan_id"]

    for bad in (other_senior, inactive):
        r = app_client.post(
            "/api/v1/events/task-assigned",
            json={"scan_id": scan_id, "assigned_to_lmo_id": str(bad.id)},
            headers=auth_headers(senior),
        )
        assert r.status_code == 422, r.text

    ok = app_client.post(
        "/api/v1/events/task-assigned",
        json={"scan_id": scan_id, "assigned_to_lmo_id": str(field.id), "instructions": "Re-inspect shelf stock"},
        headers=auth_headers(senior),
    )
    assert ok.status_code == 200, ok.text
    tasks = app_client.get("/api/v1/scans/assigned-to-me", headers=auth_headers(field)).json()
    assert tasks[0]["instructions"] == "Re-inspect shelf stock"


def test_mobile_ingest_without_timestamp_is_hash_verifiable(app_client, make_user, auth_headers, tiny_jpeg):
    officer = make_user(UserRole.FIELD_LMO)
    response = app_client.post(
        "/api/v1/scans/ingest",
        data={"lat": "13.08", "lng": "80.27", "device_id": "D1", "auto_process": "false"},
        files={"image": ("capture.jpg", io.BytesIO(tiny_jpeg), "image/jpeg")},
        headers=auth_headers(officer),
    )
    assert response.status_code == 201, response.text
    scan_id = response.json()["scan_id"]
    verify = app_client.get(f"/api/v1/scans/{scan_id}/verify-hash", headers=auth_headers(officer)).json()
    assert verify["is_valid"] is True
