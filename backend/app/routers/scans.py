"""Scan endpoints: ingest (mobile + e-commerce), queue listing, detail, review, hash verification."""
import logging
import uuid
from datetime import datetime, timedelta, timezone

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
from sqlalchemy import Text, func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_senior_lmo
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.enums import RuleStatus, ScanSource, ScanStatus, UserRole
from app.models.extracted_field import ExtractedField
from app.models.scan import Scan
from app.models.user import User
from app.schemas.scan import (
    AssignedScanItem,
    DashboardStatsResponse,
    HashVerificationResponse,
    ReviewSubmitRequest,
    ReviewSubmitResponse,
    ScanDetailResponse,
    ScanIngestResponse,
    ScanListItem,
    ScanListResponse,
)
from app.services.audit import log_audit, log_status_change
from app.services.district import known_districts, normalise_district, resolve_district_label
from app.services.events import emit_scan_status_changed
from app.services.hash_vault import compute_section_65b_hash
from app.services.pipeline_orchestrator import process_queued_scans, process_scan
from app.services.storage import get_storage_provider
from app.services.uploads import read_validated_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scans", tags=["scans"])


def _assert_can_view(scan: Scan, user: User) -> None:
    """Field officers may only read scans they captured or were assigned; seniors/admins read all."""
    if user.role == UserRole.FIELD_LMO and user.id not in (scan.captured_by_id, scan.assigned_lmo_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this scan")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_scan_list_item(
    scan: Scan, now: datetime, db: Session | None = None, users: dict | None = None
) -> ScanListItem:
    """Build a compact queue item from a Scan ORM object."""
    # Product identity: officer-entered name first, then extracted brand / manufacturer.
    product_name: str | None = scan.product_name
    net_quantity: str | None = None
    confidences = []
    for ef in scan.extracted_fields:
        if ef.field_name in ("product_name", "brand_name") and ef.raw_text and product_name is None:
            product_name = ef.raw_text
        if ef.field_name == "net_quantity" and ef.raw_text and net_quantity is None:
            net_quantity = ef.raw_text
        if ef.ocr_confidence is not None:
            confidences.append(ef.ocr_confidence)
    if product_name is None:
        for ef in scan.extracted_fields:
            if ef.field_name == "manufacturer_name" and ef.raw_text:
                product_name = ef.raw_text
                break

    confidence_gap: float | None = None
    if len(confidences) >= 2:
        confidence_gap = round(max(confidences) - min(confidences), 4)
    elif len(confidences) == 1:
        confidence_gap = 0.0

    age_hours: float | None = None
    if scan.created_at:
        delta = now - scan.created_at.replace(tzinfo=timezone.utc) if scan.created_at.tzinfo is None else now - scan.created_at
        age_hours = round(delta.total_seconds() / 3600, 2)

    district_label = resolve_district_label(scan, db, users)

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
        net_quantity=net_quantity,
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
    status_filter: ScanStatus | None = Query(None, alias="status"),
    district: str | None = Query(None),
    source: ScanSource | None = Query(None),
    q: str | None = Query(None, description="Search query for product name, field, or scan ID"),
    confidence_band: str | None = Query(
        None,
        pattern="^(critical|moderate|low)$",
        description="Filter by OCR confidence gap: critical ≥30%, moderate 15–30%, low <15%",
    ),
    age_band: str | None = Query(
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
    """Paginated scan list for the Review Queue.

    Status, source, free-text search and the created-at sort run in SQL.  The
    district, confidence-gap and age facets are derived per row, so they are
    applied after the SQL filter over the (already narrowed) candidate set.
    """
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
                Scan.product_name.ilike(search_term),
                Scan.extracted_fields.any(ExtractedField.raw_text.ilike(search_term)),
                func.cast(Scan.scan_id, Text).ilike(search_term),
            )
        )
    if age_band == "today":
        query = query.filter(Scan.created_at >= datetime.now(timezone.utc) - timedelta(hours=24))
    elif age_band == "older":
        query = query.filter(Scan.created_at < datetime.now(timezone.utc) - timedelta(hours=24))

    needs_derived_filter = bool(confidence_band) or bool(district and district.strip() and district.lower() != "all")
    needs_derived_sort = sort_by == "confidence_gap"
    order = Scan.created_at.desc() if sort_dir == "desc" else Scan.created_at.asc()
    query = query.order_by(order)

    now = datetime.now(timezone.utc)
    if not needs_derived_filter and not needs_derived_sort:
        total = query.order_by(None).count()
        page_scans = query.offset((page - 1) * page_size).limit(page_size).all()
        users = _preload_officers(db, page_scans)
        items = [_derive_scan_list_item(s_, now, db, users) for s_ in page_scans]
        return ScanListResponse(items=items, total=total, page=page, page_size=page_size)

    # Derived facets: evaluate over the SQL-narrowed set (bounded for safety).
    all_scans = query.limit(2000).all()
    users = _preload_officers(db, all_scans)
    items = [_derive_scan_list_item(s_, now, db, users) for s_ in all_scans]

    if district and district.strip() and district.lower() != "all":
        wanted = normalise_district(district)
        items = [item for item in items if normalise_district(item.district_label) == wanted]

    if confidence_band == "critical":
        items = [item for item in items if (item.confidence_gap or 0) >= 0.30]
    elif confidence_band == "moderate":
        items = [item for item in items if 0.15 <= (item.confidence_gap or 0) < 0.30]
    elif confidence_band == "low":
        items = [item for item in items if (item.confidence_gap or 0) < 0.15]

    if needs_derived_sort:
        items.sort(key=lambda x: (x.confidence_gap or 0), reverse=(sort_dir == "desc"))

    total = len(items)
    paginated = items[(page - 1) * page_size : page * page_size]
    return ScanListResponse(items=paginated, total=total, page=page, page_size=page_size)


def _preload_officers(db: Session, scans: list[Scan]) -> dict:
    """One query for every officer referenced by the page instead of one per scan."""
    ids = {sid for s_ in scans for sid in (s_.captured_by_id, s_.assigned_lmo_id) if sid}
    if not ids:
        return {}
    return {u.id: u for u in db.query(User).filter(User.id.in_(ids)).all()}


# ---------------------------------------------------------------------------
# GET /scans/districts  — filter options for the queue (must come before /{scan_id})
# ---------------------------------------------------------------------------

@router.get("/districts", response_model=list[str])
def list_districts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_senior_lmo),
):
    """Districts officers are posted to, plus the city labels GPS resolution can produce."""
    return known_districts(db)


# ---------------------------------------------------------------------------
# POST /scans/ingest  — field mobile ingestion (authenticated)
# ---------------------------------------------------------------------------

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
    product_type: str | None = Form(None, pattern="^(box|bottle|other)$"),
    product_name: str | None = Form(None, max_length=200),
    source: ScanSource | None = Form(ScanSource.MOBILE),
    auto_process: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ingest a field mobile scan.

    Computes Section 65B cryptographic hash, uploads image to object storage,
    persists scan record with status QUEUED, and logs audit event.  The
    authenticated officer is recorded as ``captured_by_id`` (chain of custody).
    """
    image_bytes, content_type, filename = await read_validated_image(image)
    # The capture timestamp is part of the Section 65B canonical payload: the
    # value that is hashed must be exactly the value that is persisted.
    now_utc = datetime.now(timezone.utc)
    if captured_at_utc is None:
        captured_at_utc = now_utc
    elif captured_at_utc.tzinfo is None:
        captured_at_utc = captured_at_utc.replace(tzinfo=timezone.utc)

    evidence_hash = compute_section_65b_hash(
        image_bytes=image_bytes,
        lat=lat,
        lng=lng,
        captured_at_utc=captured_at_utc,
        device_id=device_id
    )

    storage = get_storage_provider()
    image_url = storage.upload_file(
        file_bytes=image_bytes,
        filename=filename,
        content_type=content_type
    )

    scan_id = uuid.uuid4()
    scan = Scan(
        scan_id=scan_id,
        source=source or ScanSource.MOBILE,
        image_url=image_url,
        evidence_hash=evidence_hash,
        lat=lat,
        lng=lng,
        captured_at_utc=captured_at_utc,
        status=ScanStatus.QUEUED,
        captured_by_id=current_user.id,
        reference_object_type=reference_object_type,
        product_type=product_type,
        product_name=(product_name or "").strip() or None,
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
        actor_id=current_user.id,
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
    package_depth_mm: float | None = Form(None),
    declared_net_quantity: str | None = Form(None),
    platform_url: str | None = Form(None),
    product_name: str | None = Form(None, max_length=200),
    auto_process: bool = Form(True),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_senior_lmo),
):
    """E-commerce screenshot ingestion.

    Manual dimensions replace the reference-card calibration ratio — per §3.2, the
    mm_per_px equivalent is computed from declared physical dimensions rather than
    the reference card. Rest of the pipeline (Module 2 + 3) is unchanged.
    """
    if not (0 < package_height_mm <= 5000 and 0 < package_width_mm <= 5000):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Package dimensions must be between 0 and 5000 mm")
    image_bytes, content_type, filename = await read_validated_image(image)

    # The capture timestamp is part of the Section 65B canonical payload, so the
    # same value must be hashed and persisted.
    now_utc = datetime.now(timezone.utc)
    # For e-commerce screenshots, GPS is the web server's — not evidentiary, set null
    evidence_hash = compute_section_65b_hash(
        image_bytes=image_bytes,
        lat=None,
        lng=None,
        captured_at_utc=now_utc,
        device_id=f"web:{current_user.id}"
    )

    storage = get_storage_provider()
    image_url = storage.upload_file(
        file_bytes=image_bytes,
        filename=filename,
        content_type=content_type
    )

    # §3.2 Manual Dimension Calibration Path:
    # Instead of detecting a reference card, physical dimensions (package_height_mm, package_width_mm)
    # are mapped to the screenshot pixels to compute the exact mm_per_px calibration ratio and PDP area.
    # This feeds directly into the same downstream spatial calibration pipeline without a separate pipeline.
    mm_per_px_val: float | None = None
    pdp_area_val: float | None = None

    try:
        import io

        from PIL import Image as PILImage
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
        status=ScanStatus.QUEUED,
        captured_by_id=current_user.id,
        platform=platform.strip() or None,
        product_name=(product_name or "").strip() or None,
        reference_object_type="manual",
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

    if auto_process and background_tasks is not None:
        background_tasks.add_task(process_scan, scan.scan_id)

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
    current_user: User = Depends(require_senior_lmo),
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
    current_user: User = Depends(require_senior_lmo),
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


@router.get("/assigned-to-me", response_model=list[AssignedScanItem])
def get_scans_assigned_to_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve all scans assigned to the authenticated officer for field follow-up per §5.3."""
    scans = (
        db.query(Scan)
        .options(
            joinedload(Scan.extracted_fields),
            joinedload(Scan.rule_results),
        )
        .filter(Scan.assigned_lmo_id == current_user.id)
        .order_by(Scan.created_at.desc())
        .all()
    )

    items: list[AssignedScanItem] = []
    for s in scans:
        product_name = None
        platform = None
        instructions = None
        rule_violations: list[str] = []

        product_name = s.product_name
        platform = s.platform
        for ef in s.extracted_fields:
            if ef.field_name in ("product_name", "brand_name", "manufacturer_name") and ef.raw_text and product_name is None:
                product_name = ef.raw_text

        for rr in s.rule_results:
            if rr.status == RuleStatus.FAIL:
                rule_violations.append(f"{rr.rule_id}: {rr.reason or 'Statutory declaration non-compliant'}")

        if s.reviewer_note:
            instructions = s.reviewer_note
        elif rule_violations:
            instructions = f"Verify packaging on-site and serve notice: {', '.join(rule_violations)}"
        else:
            instructions = "Conduct on-site inspection and verify declared package credentials."

        items.append(
            AssignedScanItem(
                scan_id=s.scan_id,
                source=s.source,
                status=s.status,
                image_url=s.image_url,
                product_name=product_name or ("E-commerce listing" if s.source == ScanSource.ECOMMERCE else "Field inspection item"),
                platform=platform,
                task_type="field_followup",
                assigned_at_utc=s.created_at,
                reviewer_note=s.reviewer_note,
                instructions=instructions,
                rule_violations=rule_violations,
            )
        )

    return items


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
    _assert_can_view(scan, current_user)

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

    if scan.status in (ScanStatus.QUEUED, ScanStatus.PROCESSING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This scan is still being processed; wait for the automated verdict before reviewing",
        )
    if scan.status in (ScanStatus.PASSED, ScanStatus.FAILED) and current_user.role != UserRole.ADMIN and scan.reviewer_note:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This scan already carries a reviewed verdict; only an administrator can re-adjudicate it",
        )

    old_status = scan.status
    original_field_lmo_id = scan.assigned_lmo_id
    scan.status = body.decision
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

    # Emit scan.status_changed event per §6.2
    rule_summaries = [
        {
            "rule_id": rr.rule_id,
            "status": rr.status.value if hasattr(rr.status, "value") else str(rr.status),
            "reason": rr.reason,
        }
        for rr in (scan.rule_results or [])
    ]
    district_label = resolve_district_label(scan, db)
    try:
        emit_scan_status_changed(
            db=db,
            scan_id=scan.scan_id,
            new_status=scan.status.value,
            rule_results=rule_summaries,
            assigned_lmo_id=scan.captured_by_id or original_field_lmo_id or scan.assigned_lmo_id,
            district=district_label,
        )
    except Exception as event_err:  # event delivery must never block a legal decision
        logger.warning("Failed to emit scan.status_changed for %s: %s", scan.scan_id, event_err)

    return ReviewSubmitResponse(
        scan_id=scan.scan_id,
        new_status=scan.status,
        reviewer_note=scan.reviewer_note,
        message="Review submitted successfully"
    )



# ---------------------------------------------------------------------------
# GET /scans/{scan_id}/verify-hash  — Section 65B hash verification
# ---------------------------------------------------------------------------

@router.get("/{scan_id}/verify-hash", response_model=HashVerificationResponse)
def verify_scan_hash(
    scan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verify Section 65B digital evidence integrity.
    
    Recomputes the cryptographic hash from the original image bytes in storage
    and the canonical payload components (GPS, timestamp, device_id).
    """
    scan = db.query(Scan).filter(Scan.scan_id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    _assert_can_view(scan, current_user)

    # The ingest audit entry holds the device_id that was part of the canonical payload.
    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.target_id == str(scan_id),
            AuditLog.action.in_(["SCAN_INGESTED", "SCAN_INGESTED_DERIVED"]),
        )
        .order_by(AuditLog.timestamp.asc())
        .first()
    )
    
    device_id = None
    if audit and audit.detail:
        if audit.action == "SCAN_INGESTED":
            device_id = audit.detail.get("device_id")
        elif audit.action == "SCAN_INGESTED_DERIVED":
            device_id = f"web:{audit.actor_id}"

    storage = get_storage_provider()
    try:
        image_bytes = storage.get_file(scan.image_url)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Original image file not found in storage"
        )
        
    # Recompute the hash
    # SQLite might return a naive datetime; ensure it's UTC before hashing.
    dt = scan.captured_at_utc
    if dt and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    computed = compute_section_65b_hash(
        image_bytes=image_bytes,
        lat=scan.lat,
        lng=scan.lng,
        captured_at_utc=dt,
        device_id=device_id
    )
    
    return HashVerificationResponse(
        scan_id=scan.scan_id,
        is_valid=(computed == scan.evidence_hash),
        expected_hash=scan.evidence_hash,
        computed_hash=computed
    )

