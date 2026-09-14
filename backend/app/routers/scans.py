"""Phase 4: full scan router — ingest, list (queue), detail, review, ingest-derived."""
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

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
from sqlalchemy import func, case, and_, or_, Text

from app.db.session import get_db
from app.models.scan import Scan
from app.models.extracted_field import ExtractedField
from app.models.enums import ScanSource, ScanStatus, RuleStatus
from app.models.user import User
from app.schemas.scan import (
    ScanIngestResponse,
    ScanDetailResponse,
    ScanListResponse,
    ScanListItem,
    ReviewSubmitRequest,
    ReviewSubmitResponse,
    DashboardStatsResponse,
    IngestDerivedRequest,
)
from app.services.storage import get_storage_provider
from app.services.hash_vault import compute_section_65b_hash
from app.services.audit import log_audit, log_status_change
from app.services.pipeline_orchestrator import process_queued_scans, process_scan
from app.core.deps import get_current_user, require_senior_lmo
router = APIRouter(prefix="/scans", tags=["scans"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_district_label(scan: Scan, db: Optional[Session] = None) -> Optional[str]:
    """Resolve human-readable district label from assigned officer or GPS coordinates."""
    if scan.assigned_lmo_id and db:
        user = db.query(User).filter(User.id == scan.assigned_lmo_id).first()
        if user and user.district:
            return user.district

    if scan.lat is not None and scan.lng is not None:
        lat, lng = scan.lat, scan.lng
        if 12.8 <= lat <= 13.4 and 79.8 <= lng <= 80.5:
            return "Chennai, TN"
        elif 10.7 <= lat <= 11.4 and 76.7 <= lng <= 77.4:
            return "Coimbatore, TN"
        elif 9.6 <= lat <= 10.2 and 77.8 <= lng <= 78.4:
            return "Madurai, TN"
        elif 11.4 <= lat <= 11.9 and 77.9 <= lng <= 78.4:
            return "Salem, TN"
        return f"{lat:.2f}N, {lng:.2f}E"

    return None


def _derive_scan_list_item(scan: Scan, now: datetime, db: Optional[Session] = None) -> ScanListItem:
    """Build a compact queue item from a Scan ORM object."""
    # Best-effort product name from extracted fields
    product_name: Optional[str] = None
    confidences = []
    for ef in scan.extracted_fields:
        if ef.field_name in ("net_quantity", "brand_name", "product_name") and ef.raw_text:
            if product_name is None:
                product_name = ef.raw_text
        if ef.ocr_confidence is not None:
            confidences.append(ef.ocr_confidence)

    confidence_gap: Optional[float] = None
    if len(confidences) >= 2:
        confidence_gap = round(max(confidences) - min(confidences), 4)
    elif len(confidences) == 1:
        confidence_gap = 0.0

    age_hours: Optional[float] = None
    if scan.created_at:
        delta = now - scan.created_at.replace(tzinfo=timezone.utc) if scan.created_at.tzinfo is None else now - scan.created_at
        age_hours = round(delta.total_seconds() / 3600, 2)

    district_label = _resolve_district_label(scan, db)

    return ScanListItem(
        scan_id=scan.scan_id,
        source=scan.source,
        status=scan.status,
        image_url=scan.image_url,
        lat=scan.lat,
        lng=scan.lng,
        captured_at_utc=scan.captured_at_utc,
        created_at=scan.created_at,
        product_name=product_name,
        district_label=district_label,
        confidence_gap=confidence_gap,
        age_hours=age_hours,
    )


# ---------------------------------------------------------------------------
# GET /scans/stats  — dashboard overview counts (must come before /{scan_id})
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_senior_lmo),
):
    """Return today's scanned/passed/failed/pending counts for the Overview screen."""
    today_utc = datetime.now(timezone.utc).date()
    today_start = datetime.combine(today_utc, datetime.min.time()).replace(tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)

    # Today's counts per status
    today_counts = (
        db.query(Scan.status, func.count(Scan.scan_id).label("cnt"))
        .filter(Scan.created_at >= today_start, Scan.created_at < today_end)
        .group_by(Scan.status)
        .all()
    )
    counts_map = {row.status: row.cnt for row in today_counts}

    # Total queue depth (pending review is not just today's — it's everything backlogged)
    pending_total = (
        db.query(func.count(Scan.scan_id))
        .filter(Scan.status == ScanStatus.PENDING_REVIEW)
        .scalar()
    ) or 0

    return DashboardStatsResponse(
        scanned_today=sum(counts_map.values()),
        passed_today=counts_map.get(ScanStatus.PASSED, 0),
        failed_today=counts_map.get(ScanStatus.FAILED, 0),
        pending_review=pending_total,
        calibration_failed_today=counts_map.get(ScanStatus.CALIBRATION_FAILED, 0),
    )


# ---------------------------------------------------------------------------
# GET /scans/  — paginated queue, filterable
# ---------------------------------------------------------------------------

@router.get("/", response_model=ScanListResponse)
def list_scans(
    status_filter: Optional[ScanStatus] = Query(None, alias="status"),
    district: Optional[str] = Query(None),
    source: Optional[ScanSource] = Query(None),
    q: Optional[str] = Query(None, description="Search query for product name, field, or scan ID"),
    confidence_band: Optional[str] = Query(
        None,
        pattern="^(critical|moderate|low)$",
        description="Filter by OCR confidence gap: critical ≥30%, moderate 15–30%, low <15%",
    ),
    age_band: Optional[str] = Query(
        None,
        pattern="^(today|older)$",
        description="Filter by scan age: today <24h, older ≥24h",
    ),
    sort_by: str = Query("created_at", pattern="^(created_at|confidence_gap|age)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_senior_lmo),
):
    """Paginated scan list for the Review Queue. Supports filtering and sorting."""
    query = db.query(Scan).options(
        joinedload(Scan.extracted_fields),
        joinedload(Scan.rule_results),
    )

    if status_filter:
        query = query.filter(Scan.status == status_filter)
    if source:
        query = query.filter(Scan.source == source)

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Scan.extracted_fields.any(ExtractedField.raw_text.ilike(search_term)),
                func.cast(Scan.scan_id, Text).ilike(search_term)
            )
        )

    all_scans = query.all()
    now = datetime.now(timezone.utc)
    items = [_derive_scan_list_item(s, now, db) for s in all_scans]

    # Filter by district if specified
    if district and district.strip() and district.lower() != "all":
        d_lower = district.strip().lower()
        items = [item for item in items if item.district_label and d_lower in item.district_label.lower()]

    if confidence_band == "critical":
        items = [item for item in items if (item.confidence_gap or 0) >= 0.30]
    elif confidence_band == "moderate":
        items = [
            item for item in items
            if 0.15 <= (item.confidence_gap or 0) < 0.30
        ]
    elif confidence_band == "low":
        items = [item for item in items if (item.confidence_gap or 0) < 0.15]

    if age_band == "today":
        items = [item for item in items if (item.age_hours or 0) < 24]
    elif age_band == "older":
        items = [item for item in items if (item.age_hours or 0) >= 24]

    total = len(items)

    # Sorting
    if sort_by == "confidence_gap":
        items.sort(
            key=lambda x: (x.confidence_gap or 0),
            reverse=(sort_dir == "desc")
        )
    else:
        # created_at or age
        items.sort(
            key=lambda x: x.created_at,
            reverse=(sort_dir == "desc")
        )

    paginated = items[(page - 1) * page_size : page * page_size]

    return ScanListResponse(
        items=paginated,
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# POST /scans/ingest  — standard mobile ingestion (unchanged)
# ---------------------------------------------------------------------------

@router.post("/ingest", response_model=ScanIngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_scan(
    request: Request,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    captured_at_utc: Optional[datetime] = Form(None),
    device_id: Optional[str] = Form(None),
    reference_object_type: Optional[str] = Form(None),
    source: Optional[ScanSource] = Form(ScanSource.MOBILE),
    auto_process: bool = Form(True),
    db: Session = Depends(get_db),
):
    """Ingest a field mobile scan.

    Computes Section 65B cryptographic hash, uploads image to object storage,
    persists scan record with status QUEUED, and logs audit event.
    """
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty"
        )

    evidence_hash = compute_section_65b_hash(
        image_bytes=image_bytes,
        lat=lat,
        lng=lng,
        captured_at_utc=captured_at_utc,
        device_id=device_id
    )

    storage = get_storage_provider()
    filename = image.filename or "capture.jpg"
    content_type = image.content_type or "image/jpeg"
    image_url = storage.upload_file(
        file_bytes=image_bytes,
        filename=filename,
        content_type=content_type
    )

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
        status=ScanStatus.QUEUED,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

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



# ---------------------------------------------------------------------------
# POST /scans/ingest-derived  — e-commerce path (manual dimensions)
# ---------------------------------------------------------------------------

@router.post("/ingest-derived", response_model=ScanIngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_derived_scan(
    request: Request,
    image: UploadFile = File(...),
    platform: str = Form(...),
    package_height_mm: float = Form(...),
    package_width_mm: float = Form(...),
    package_depth_mm: Optional[float] = Form(None),
    declared_net_quantity: Optional[str] = Form(None),
    platform_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_senior_lmo),
):
    """E-commerce screenshot ingestion.

    Manual dimensions replace the reference-card calibration ratio — per §3.2, the
    mm_per_px equivalent is computed from declared physical dimensions rather than
    the reference card. Rest of the pipeline (Module 2 + 3) is unchanged.
    """
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty"
        )

    # For e-commerce screenshots, GPS is the web server's — not evidentiary, set null
    evidence_hash = compute_section_65b_hash(
        image_bytes=image_bytes,
        lat=None,
        lng=None,
        captured_at_utc=datetime.now(timezone.utc),
        device_id=f"web:{current_user.id}"
    )

    storage = get_storage_provider()
    filename = image.filename or "ecommerce_screenshot.jpg"
    content_type = image.content_type or "image/jpeg"
    image_url = storage.upload_file(
        file_bytes=image_bytes,
        filename=filename,
        content_type=content_type
    )

    now_utc = datetime.now(timezone.utc)
    # §3.2 Manual Dimension Calibration Path:
    # Instead of detecting a reference card, physical dimensions (package_height_mm, package_width_mm)
    # are mapped to the screenshot pixels to compute the exact mm_per_px calibration ratio and PDP area.
    # This feeds directly into the same downstream spatial calibration pipeline without a separate pipeline.
    mm_per_px_val: Optional[float] = None
    pdp_area_val: Optional[float] = None

    try:
        from PIL import Image as PILImage
        import io
        img = PILImage.open(io.BytesIO(image_bytes))
        img_w, img_h = img.size
        # Long edge of the package face maps to the long dimension of the product image
        max_px = max(img_w, img_h)
        long_edge_mm = max(package_height_mm, package_width_mm)
        if max_px > 0:
            mm_per_px_val = round(long_edge_mm / max_px, 6)
        # Principal Display Panel (PDP) area in cm² = (height_mm * width_mm) / 100
        pdp_area_val = round((package_height_mm * package_width_mm) / 100.0, 2)
    except Exception:
        # Fallback if image parsing fails
        mm_per_px_val = 0.085
        pdp_area_val = round((package_height_mm * package_width_mm) / 100.0, 2)

    scan = Scan(
        scan_id=uuid.uuid4(),
        source=ScanSource.ECOMMERCE,
        image_url=image_url,
        evidence_hash=evidence_hash,
        lat=None,
        lng=None,
        captured_at_utc=now_utc,
        mm_per_px=mm_per_px_val,
        pdp_area_cm2=pdp_area_val,
        ruleset_version="2026.1",
        status=ScanStatus.QUEUED,
        assigned_lmo_id=current_user.id,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    # Store declared dimensions as an extracted field so the pipeline worker can pick them up
    dim_field = ExtractedField(
        id=uuid.uuid4(),
        scan_id=scan.scan_id,
        field_name="declared_dimensions",
        raw_text=(
            f"h:{package_height_mm}mm w:{package_width_mm}mm"
            + (f" d:{package_depth_mm}mm" if package_depth_mm else "")
            + f" | platform:{platform}"
            + (f" | qty:{declared_net_quantity}" if declared_net_quantity else "")
        ),
        bbox=None,
        ocr_confidence=1.0,    # manually entered — fully trusted
        semantic_confidence=1.0,
    )
    db.add(dim_field)
    db.commit()

    log_audit(
        db=db,
        action="SCAN_INGESTED_DERIVED",
        target_type="scan",
        target_id=str(scan.scan_id),
        actor_id=current_user.id,
        detail={
            "source": "ecommerce",
            "platform": platform,
            "platform_url": platform_url,
            "package_height_mm": package_height_mm,
            "package_width_mm": package_width_mm,
            "declared_net_quantity": declared_net_quantity,
            "evidence_hash": evidence_hash,
            "image_url": image_url,
        }
    )

    return ScanIngestResponse(
        scan_id=scan.scan_id,
        status=scan.status,
        image_url=scan.image_url,
        evidence_hash=scan.evidence_hash,
        captured_at_utc=scan.captured_at_utc,
        created_at=scan.created_at,
        message="E-commerce scan received and queued. Manual dimensions stored for pipeline calibration."
    )


# ---------------------------------------------------------------------------
# GET /scans/{scan_id}  — full detail
# ---------------------------------------------------------------------------

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
    current_user: User = Depends(get_current_user),
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



# ---------------------------------------------------------------------------
# POST /scans/{scan_id}/review  — senior LMO decision
# ---------------------------------------------------------------------------

@router.post("/{scan_id}/review", response_model=ReviewSubmitResponse)
def review_scan(
    scan_id: uuid.UUID,
    body: ReviewSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_senior_lmo),
):
    """Submit a review decision on a PENDING_REVIEW scan.

    Requires a mandatory reviewer_note — editable field overrides with no explanation
    are blocked at the schema level. Per §2.1: capture and adjudication are separated roles.
    """
    scan = db.query(Scan).filter(Scan.scan_id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    if scan.status not in (ScanStatus.PENDING_REVIEW, ScanStatus.CALIBRATION_FAILED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Scan is in status '{scan.status.value}' — only PENDING_REVIEW scans can be reviewed"
        )

    old_status = scan.status
    scan.status = body.decision
    scan.assigned_lmo_id = current_user.id
    scan.reviewer_note = body.reviewer_note

    # Apply field overrides if provided
    if body.overridden_fields:
        for field_name, corrected_value in body.overridden_fields.items():
            ef = db.query(ExtractedField).filter(
                ExtractedField.scan_id == scan_id,
                ExtractedField.field_name == field_name
            ).first()
            if ef:
                ef.raw_text = corrected_value
                # Mark overridden field as fully trusted (reviewer vouches for it)
                ef.ocr_confidence = 1.0
                ef.semantic_confidence = 1.0

    db.commit()
    db.refresh(scan)

    log_status_change(
        db=db,
        target_type="scan",
        target_id=str(scan.scan_id),
        new_status=body.decision.value,
        old_status=old_status.value,
        actor_id=current_user.id,
        action="SCAN_REVIEWED",
        detail={
            "reviewer_note": body.reviewer_note,
            "overridden_fields": list(body.overridden_fields.keys()) if body.overridden_fields else [],
            "decision": body.decision.value,
        }
    )

    return ReviewSubmitResponse(
        scan_id=scan.scan_id,
        new_status=scan.status,
        reviewer_note=scan.reviewer_note,
        message="Review submitted successfully"
    )

