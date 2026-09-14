import io
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors

from app.db.session import get_db
from app.models.scan import Scan
from app.models.challan import Challan
from app.models.user import User
from app.models.enums import ScanStatus, RuleStatus, UserRole
from app.schemas.challan import ChallanGenerateRequest, ChallanResponse, ChallanListResponse
from app.services.storage import get_storage_provider
from app.core.deps import get_current_user, require_senior_lmo
from app.services.audit import log_audit

router = APIRouter(prefix="/challans", tags=["challans"])

def draw_seal_badge_vector(c, x, y, width, height, is_pass=False):
    """Render the Seal Badge as vector per §5.1/§9."""
    c.saveState()
    color = colors.HexColor("#ef4444") if not is_pass else colors.HexColor("#22c55e")
    c.setFillColor(color)
    c.setStrokeColor(color)
    
    # Simple vector seal: a circle with text
    c.circle(x + width/2, y + height/2, min(width, height)/2, fill=0, stroke=1)
    
    c.setFont("Helvetica-Bold", 10)
    text = "PASSED" if is_pass else "VIOLATION"
    c.drawCentredString(x + width/2, y + height/2 - 3, text)
    c.restoreState()


@router.get("/", response_model=ChallanListResponse)
def list_challans(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Challan)
    
    # Field LMOs can only see challans generated for scans assigned to them
    if current_user.role == UserRole.FIELD_LMO:
        query = query.join(Scan, Scan.scan_id == Challan.scan_id).filter(Scan.assigned_lmo_id == current_user.id)
        
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_senior_lmo)
):
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

    # Block generation with explicit error if any required field is null
    failed_rules = [r for r in scan.rule_results if r.status == RuleStatus.FAIL]
    if not failed_rules:
        raise HTTPException(status_code=400, detail="No failed rules found, cannot generate challan")
    rule_texts = [f"{r.rule_id}: {r.reason}" for r in failed_rules]
    
    if scan.lat is None or scan.lng is None:
        raise HTTPException(status_code=400, detail="Incomplete record: GPS coordinates are missing")
        
    lmo_id = scan.assigned_lmo_id or current_user.id
    if not lmo_id:
        raise HTTPException(status_code=400, detail="Incomplete record: LMO ID is missing")
        
    storage = get_storage_provider()
    try:
        image_bytes = storage.get_file(scan.image_url)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Image file not found in storage")
        
    # Generate PDF
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4
    
    # 1. Government Header
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 50, "DEPARTMENT OF LEGAL METROLOGY")
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, height - 70, "Section 39 Notice of Violation")
    
    # 2. Details
    c.setFont("Helvetica", 10)
    y = height - 100
    
    dt = scan.captured_at_utc
    if dt and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts_str = dt.strftime('%Y-%m-%d %H:%M:%S UTC') if dt else "UNKNOWN"
    
    c.drawString(50, y, f"Scan ID: {scan.scan_id}")
    c.drawString(50, y - 15, f"Date: {ts_str}")
    c.drawString(50, y - 30, f"Location (GPS): {scan.lat:.6f}, {scan.lng:.6f}")
    c.drawString(50, y - 45, f"LMO ID: {lmo_id}")
    c.drawString(50, y - 60, f"Section 65B Hash: {scan.evidence_hash}")
    
    # 3. Rules Broken
    y -= 90
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Violations Detected:")
    c.setFont("Helvetica", 10)
    y -= 15
    for rt in rule_texts:
        c.drawString(60, y, f"- {rt}")
        y -= 15
        
    # 4. Seal Badge Vector
    draw_seal_badge_vector(c, width - 120, height - 120, 60, 60, is_pass=False)
    
    # 5. Original Image (Untouched)
    from PIL import Image as PILImage
    import tempfile
    
    img = PILImage.open(io.BytesIO(image_bytes))
    img_w, img_h = img.size
    
    # Save temp image for reportlab
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
        # reportlab works best with RGB not RGBA
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(tf.name)
        tmp_img_path = tf.name
        
    # Draw original image
    # Scale to fit half width
    draw_w = 200
    draw_h = int(img_h * (draw_w / img_w))
    c.drawString(50, y - 20, "Original Evidentiary Image:")
    c.drawImage(tmp_img_path, 50, y - 20 - draw_h, width=draw_w, height=draw_h)
    
    # 6. Annotated Crop
    c.drawString(300, y - 20, "Annotated Copy:")
    c.drawImage(tmp_img_path, 300, y - 20 - draw_h, width=draw_w, height=draw_h)
    
    # Draw bounding boxes dynamically as vectors on top of the annotated copy
    c.setStrokeColor(colors.red)
    c.setLineWidth(1.5)
    
    scale = draw_w / img_w
    for ef in scan.extracted_fields:
        if ef.bbox and len(ef.bbox) == 4:
            bx, by, bw, bh = ef.bbox
            # Map original coordinates to PDF coordinates
            rect_x = 300 + (bx * scale)
            # PDF coordinates go from bottom to top, so invert Y relative to the image bounding box
            rect_y = (y - 20 - draw_h) + draw_h - (by * scale) - (bh * scale)
            rect_w = bw * scale
            rect_h = bh * scale
            c.rect(rect_x, rect_y, rect_w, rect_h, stroke=1, fill=0)
            
    c.showPage()
    c.save()
    
    pdf_bytes = pdf_buffer.getvalue()
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
    
    # Clean up temp file
    import os
    try:
        os.remove(tmp_img_path)
    except:
        pass
        
    return ChallanResponse.model_validate(challan)
