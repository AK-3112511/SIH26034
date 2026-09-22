"""Seed demonstration scans by running the *real* pipeline.

Run from /backend (after ``seed_users`` and ``seed_rulesets``)::

    python -m app.db.seed_scans            # renders the demo catalogue and processes it
    python -m app.db.seed_scans --reset    # deletes previously seeded demo scans first

Each demo label is rendered as a photo (package face + ISO/IEC 7810 card),
ingested exactly like a mobile capture (hash, storage, audit) attributed to a
seeded field officer at a real district location, and then processed by the
same OCR → calibration → rule-engine path production uses.  Nothing about the
verdict is typed in by hand, so what the dashboard shows is what the system
actually concluded.
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone

import cv2
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.enums import ScanSource, ScanStatus, UserRole
from app.models.scan import Scan
from app.models.user import User
from app.services.audit import log_audit
from app.services.district import normalise_district
from app.services.hash_vault import compute_section_65b_hash
from app.services.pipeline_orchestrator import process_scan
from app.services.storage import get_storage_provider
from app.services.vision.synthetic import DEMO_LABELS, render_label_with_card

SEED_DEVICE_ID = "demo-seed-device"

# Retail locations across the officers' districts (lat, lng, place).
_LOCATIONS = [
    (13.0418, 80.2341, "T. Nagar market, Chennai"),
    (11.0168, 76.9558, "RS Puram, Coimbatore"),
    (9.9252, 78.1198, "Meenakshi Bazaar, Madurai"),
    (11.6643, 78.1460, "Five Roads, Salem"),
    (13.0827, 80.2707, "Parrys Corner, Chennai"),
]


def _pick_officer(db: Session, index: int, place: str) -> User:
    """Prefer the officer posted to the district the capture happened in."""
    officers = db.query(User).filter(User.role == UserRole.FIELD_LMO, User.is_active.is_(True)).order_by(User.username).all()
    if not officers:
        raise SystemExit("No active field officers found — run `python -m app.db.seed_users` first")
    city = normalise_district(place.split(",")[-1])
    for officer in officers:
        if normalise_district(officer.district) == city:
            return officer
    return officers[index % len(officers)]


def reset_demo_scans(db: Session) -> int:
    ids = [
        row[0]
        for row in db.query(AuditLog.target_id)
        .filter(AuditLog.action == "SCAN_INGESTED", AuditLog.detail["device_id"].as_string() == SEED_DEVICE_ID)
        .all()
    ]
    removed = 0
    for sid in ids:
        try:
            scan = db.query(Scan).filter(Scan.scan_id == uuid.UUID(sid)).first()
        except ValueError:
            continue
        if scan:
            db.delete(scan)
            removed += 1
    db.commit()
    return removed


def seed_demo_scans(db: Session, verbose: bool = True) -> list[Scan]:
    storage = get_storage_provider()
    created: list[Scan] = []
    now = datetime.now(timezone.utc)

    for index, (name, spec) in enumerate(DEMO_LABELS):
        lat, lng, place = _LOCATIONS[index % len(_LOCATIONS)]
        officer = _pick_officer(db, index, place)
        image, _geometry = render_label_with_card(spec, seed=index)
        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        if not ok:
            raise RuntimeError(f"could not encode demo image {name}")
        image_bytes = encoded.tobytes()
        captured_at = now - timedelta(hours=index * 3 + 1)

        evidence_hash = compute_section_65b_hash(
            image_bytes=image_bytes, lat=lat, lng=lng, captured_at_utc=captured_at, device_id=SEED_DEVICE_ID
        )
        image_key = storage.upload_file(image_bytes, f"demo_{name}.jpg", content_type="image/jpeg")
        scan = Scan(
            scan_id=uuid.uuid4(),
            source=ScanSource.MOBILE,
            image_url=image_key,
            evidence_hash=evidence_hash,
            lat=lat,
            lng=lng,
            captured_at_utc=captured_at,
            status=ScanStatus.QUEUED,
            captured_by_id=officer.id,
            reference_object_type="debit_card",
            product_type="box",
            product_name=f"{spec.brand.title()} {spec.product}",
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)
        log_audit(
            db=db,
            action="SCAN_INGESTED",
            target_type="scan",
            target_id=str(scan.scan_id),
            actor_id=officer.id,
            detail={
                "status": ScanStatus.QUEUED.value,
                "source": ScanSource.MOBILE.value,
                "device_id": SEED_DEVICE_ID,
                "reference_object_type": "debit_card",
                "evidence_hash": evidence_hash,
                "image_url": image_key,
                "ip_address": "seed",
                "place": place,
            },
        )

        processed = process_scan(scan.scan_id, db=db)
        created.append(processed or scan)
        if verbose:
            status = processed.status.value if processed else "?"
            print(f"  - {name:24s} -> {status:14s} ({officer.username} @ {place})")

    return created


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--reset", action="store_true", help="delete previously seeded demo scans first")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        if args.reset:
            print(f"Removed {reset_demo_scans(session)} previously seeded demo scan(s)")
        print("Rendering demo labels and running the real pipeline (first run loads OCR models)...")
        seed_demo_scans(session)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        raise
    finally:
        session.close()
