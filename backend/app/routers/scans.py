import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.enums import ScanSource, ScanStatus
from app.models.scan import Scan
from app.schemas.scan import ScanDetailResponse, ScanIngestResponse
from app.services.audit import log_audit
from app.services.hash_vault import compute_section_65b_hash
from app.services.pipeline_orchestrator import process_queued_scans, process_scan
from app.services.storage import get_storage_provider

router = APIRouter(prefix="/scans", tags=["scans"])

@router.post("/ingest", response_model=ScanIngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_scan(
    request: Request,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    captured_at_utc: datetime | None = Form(None),
    device_id: str | None = Form(None),
    reference_object_type: str | None = Form(None),
    source: ScanSource | None = Form(ScanSource.MOBILE),
    auto_process: bool = Form(True),
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
            "ip_address": client_ip,
        },
    )

    # Dispatch full processing pipeline asynchronously if auto_process is enabled
    if auto_process:
        background_tasks.add_task(process_scan, scan.scan_id)

    return ScanIngestResponse(
        scan_id=scan.scan_id,
        status=scan.status,
        image_url=scan.image_url,
        evidence_hash=scan.evidence_hash,
        captured_at_utc=scan.captured_at_utc,
        created_at=scan.created_at,
        message="Scan received and queued for processing",
    )


@router.post("/{scan_id}/process", response_model=ScanDetailResponse)
def trigger_scan_process(
    scan_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Synchronously triggers or re-runs the full MetrologyAI pipeline (Phases 3.1 -> 3.5)
    on a scan, returning real extracted fields, spatial measurements, and rule results.
    """
    processed_scan = process_scan(scan_id=scan_id, db=db)
    if not processed_scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan with ID '{scan_id}' not found",
        )

    # Re-fetch with relationships loaded
    scan = (
        db.query(Scan)
        .options(
            joinedload(Scan.extracted_fields),
            joinedload(Scan.rule_results),
        )
        .filter(Scan.scan_id == scan_id)
        .first()
    )
    return ScanDetailResponse.model_validate(scan)


@router.post("/process-queued", response_model=list[ScanDetailResponse])
def trigger_batch_process_queued(
    limit: int = Query(10, ge=1, le=100, description="Max queued scans to process"),
    db: Session = Depends(get_db),
):
    """
    Batch processes pending QUEUED scans up to limit and returns updated records.
    """
    processed_scans = process_queued_scans(limit=limit, db=db)
    results: list[ScanDetailResponse] = []
    for s in processed_scans:
        full_scan = (
            db.query(Scan)
            .options(
                joinedload(Scan.extracted_fields),
                joinedload(Scan.rule_results),
            )
            .filter(Scan.scan_id == s.scan_id)
            .first()
        )
        if full_scan:
            results.append(ScanDetailResponse.model_validate(full_scan))
    return results


@router.get("/{scan_id}", response_model=ScanDetailResponse)
def get_scan(
    scan_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieve scan status, evidence details, extracted fields, and rule results."""
    scan = (
        db.query(Scan)
        .options(
            joinedload(Scan.extracted_fields),
            joinedload(Scan.rule_results),
        )
        .filter(Scan.scan_id == scan_id)
        .first()
    )

    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan with ID '{scan_id}' not found",
        )

    return ScanDetailResponse.model_validate(scan)

