import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_senior_lmo
from app.db.session import get_db
from app.models.challan import Challan
from app.models.enums import RuleStatus, ScanSource, ScanStatus, UserRole
from app.models.scan import Scan
from app.models.user import User
from app.schemas.challan import ChallanGenerateRequest, ChallanListResponse, ChallanResponse
from app.services.audit import log_audit
from app.services.challan_pdf import ChallanContext, render_challan_pdf
from app.services.district import resolve_district_label
from app.services.storage import get_storage_provider

router = APIRouter(prefix="/challans", tags=["challans"])

# Which extracted declarations each rule adjudicates (for highlighting on the notice).
RULE_FIELDS = {
    "6.1.a": ("manufacturer_name", "manufacturer_address", "pincode"),
    "6.1.c": ("net_quantity", "unit"),
    "6.1.e": ("mrp",),
    "6.1.g": ("consumer_care",),
    "schedule_ii": ("net_quantity",),
}
FIELD_ORDER = {name: i for i, name in enumerate((
    "product_name", "net_quantity", "unit", "mrp", "mfg_date", "manufacturer_name",
    "manufacturer_address", "pincode", "consumer_care",
))}


@router.get("/", response_model=ChallanListResponse)
def list_challans(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    scan_id: uuid.UUID | None = Query(
        None, description="Return only the notice issued for this scan, if any."
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Challan)

    # The scan detail screen asks "has a notice already been issued?" — it must
    # be able to find out with a read rather than by attempting to generate one.
    if scan_id is not None:
        query = query.filter(Challan.scan_id == scan_id)

    # Field LMOs only see challans for scans they captured or were assigned.
    if current_user.role == UserRole.FIELD_LMO:
        query = query.join(Scan, Scan.scan_id == Challan.scan_id).filter(
            or_(Scan.assigned_lmo_id == current_user.id, Scan.captured_by_id == current_user.id)
        )
        
    total = query.count()
    challans = query.order_by(Challan.generated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return ChallanListResponse(
        items=[ChallanResponse.model_validate(c) for c in challans],
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/generate", response_model=ChallanResponse, status_code=status.HTTP_201_CREATED)
def generate_challan(
    body: ChallanGenerateRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_senior_lmo)
):
    """Generate (or return the existing) Section 39 notice for a FAILED scan.

    One notice exists per scan; calling this again returns the stored record
    with HTTP 200 instead of issuing a duplicate legal document.
    """
    existing = db.query(Challan).filter(Challan.scan_id == body.scan_id).first()
    if existing:
        response.status_code = status.HTTP_200_OK
        return ChallanResponse.model_validate(existing)

    scan = (
        db.query(Scan)
        .options(
            joinedload(Scan.rule_results),
            joinedload(Scan.extracted_fields)
        )
        .filter(Scan.scan_id == body.scan_id)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
        
    if scan.status != ScanStatus.FAILED:
        raise HTTPException(status_code=400, detail="Cannot generate challan for non-FAILED scan")

    # Never emit a partially-filled legal document (§2.1 failure path).
    failed_rules = [r for r in scan.rule_results if r.status == RuleStatus.FAIL]
    if not failed_rules:
        raise HTTPException(status_code=400, detail="No failed rules found, cannot generate challan")
    if scan.source == ScanSource.MOBILE and (scan.lat is None or scan.lng is None):
        raise HTTPException(status_code=400, detail="Incomplete record: GPS coordinates are missing")

    # The notice names the officer who captured the evidence; for e-commerce
    # scans that is the senior officer who ingested the listing.
    lmo_id = scan.captured_by_id or scan.assigned_lmo_id or current_user.id
    officer = db.query(User).filter(User.id == lmo_id).first()

    storage = get_storage_provider()
    try:
        image_bytes = storage.get_file(scan.image_url)
    except FileNotFoundError:
        raise HTTPException(status_code=422, detail="Evidence image is missing from storage; the notice cannot be issued")

    failed_field_names = set()
    for r in failed_rules:
        failed_field_names.update(RULE_FIELDS.get(r.rule_id, ()))

    ctx = ChallanContext(
        scan_id=str(scan.scan_id),
        product_name=scan.product_name
        or next((ef.raw_text for ef in scan.extracted_fields if ef.field_name == "product_name" and ef.raw_text), None),
        source=scan.source.value,
        platform=scan.platform,
        captured_at=scan.captured_at_utc,
        lat=scan.lat,
        lng=scan.lng,
        district=resolve_district_label(scan, db),
        officer_name=officer.full_name if officer else "Officer on record",
        officer_id=str(lmo_id),
        issuing_officer_name=current_user.full_name or current_user.username,
        evidence_hash=scan.evidence_hash,
        ruleset_version=scan.ruleset_version,
        mm_per_px=scan.mm_per_px,
        pdp_area_cm2=scan.pdp_area_cm2,
        fields=[
            {
                "field_name": ef.field_name,
                "raw_text": ef.raw_text,
                "font_height_mm": ef.font_height_mm,
                "bbox": ef.bbox,
                "failed": ef.field_name in failed_field_names,
            }
            for ef in sorted(scan.extracted_fields, key=lambda e: FIELD_ORDER.get(e.field_name, 99))
        ],
        violations=[{"rule_id": r.rule_id, "reason": r.reason, "evidence": r.evidence} for r in failed_rules],
        image_bytes=image_bytes,
    )
    pdf_bytes = render_challan_pdf(ctx)
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()

    pdf_filename = f"challan_{scan.scan_id}.pdf"
    pdf_url = storage.upload_file(pdf_bytes, pdf_filename, content_type="application/pdf")

    now_utc = datetime.now(timezone.utc)
    challan = Challan(
        scan_id=scan.scan_id,
        lmo_id=lmo_id,
        pdf_url=pdf_url,
        pdf_hash=pdf_hash,
        generated_at=now_utc
    )
    db.add(challan)
    db.commit()
    db.refresh(challan)
    
    log_audit(
        db=db,
        action="CHALLAN_GENERATED",
        target_type="challan",
        target_id=str(challan.challan_id),
        actor_id=current_user.id,
        detail={
            "scan_id": str(scan.scan_id),
            "pdf_hash": pdf_hash,
            "pdf_url": pdf_url
        }
    )
    
    return ChallanResponse.model_validate(challan)
