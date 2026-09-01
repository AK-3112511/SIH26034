import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.scan import Scan
from app.models.enums import ScanSource, ScanStatus
from app.schemas.scan import ScanIngestResponse, ScanDetailResponse
from app.services.storage import get_storage_provider
from app.services.hash_vault import compute_section_65b_hash
from app.services.audit import log_audit, log_status_change

router = APIRouter(prefix="/scans", tags=["scans"])

@router.post("/ingest", response_model=ScanIngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_scan(
    request: Request,
    image: UploadFile = File(...),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    captured_at_utc: Optional[datetime] = Form(None),
    device_id: Optional[str] = Form(None),
    reference_object_type: Optional[str] = Form(None),
    source: Optional[ScanSource] = Form(ScanSource.MOBILE),
    db: Session = Depends(get_db)
):
    """Ingest a field mobile scan or e-commerce capture.

    Computes Section 65B cryptographic hash, uploads image to object storage,
    persists scan record with status QUEUED, and logs audit event.
    """
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty"
        )

    # Compute legal Section 65B hash binding image + metadata
    evidence_hash = compute_section_65b_hash(
        image_bytes=image_bytes,
        lat=lat,
        lng=lng,
        captured_at_utc=captured_at_utc,
        device_id=device_id
    )

    # Store image in configured storage provider (Local Disk or S3)
    storage = get_storage_provider()
    filename = image.filename or "capture.jpg"
    content_type = image.content_type or "image/jpeg"
    image_url = storage.upload_file(
        file_bytes=image_bytes,
        filename=filename,
        content_type=content_type
    )

    # Persist Scan record in database
    scan_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)
    scan = Scan(
        scan_id=scan_id,
        source=source or ScanSource.MOBILE,
        image_url=image_url,
        evidence_hash=evidence_hash,
        lat=lat,
        lng=lng,
        captured_at_utc=captured_at_utc or now_utc,
        status=ScanStatus.QUEUED
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    # Log ingestion in audit trail
    client_ip = request.client.host if request.client else "unknown"
    log_audit(
        db=db,
        action="SCAN_INGESTED",
        target_type="scan",
        target_id=str(scan.scan_id),
        detail={
            "status": scan.status.value,
            "source": scan.source.value,
            "device_id": device_id,
            "reference_object_type": reference_object_type,
            "evidence_hash": evidence_hash,
            "image_url": image_url,
            "ip_address": client_ip
        }
    )

    return ScanIngestResponse(
        scan_id=scan.scan_id,
        status=scan.status,
        image_url=scan.image_url,
        evidence_hash=scan.evidence_hash,
        captured_at_utc=scan.captured_at_utc,
        created_at=scan.created_at,
        message="Scan received and queued for processing"
    )


@router.get("/{scan_id}", response_model=ScanDetailResponse)
def get_scan(
    scan_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Retrieve scan status, evidence details, extracted fields, and rule results."""
    scan = db.query(Scan).options(
        joinedload(Scan.extracted_fields),
        joinedload(Scan.rule_results)
    ).filter(Scan.scan_id == scan_id).first()

    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan with ID '{scan_id}' not found"
        )

    return ScanDetailResponse.model_validate(scan)
