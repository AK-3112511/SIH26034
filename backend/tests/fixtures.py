"""Hand-written scan rows for API tests (NOT demo data — demo data is produced by
the real pipeline in app.db.seed_scans).

Seed script to populate realistic PENDING_REVIEW scans and test fixtures per §4.2 layout sketch."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.enums import RuleStatus, ScanSource, ScanStatus
from app.models.extracted_field import ExtractedField
from app.models.rule_result import RuleResult
from app.models.scan import Scan


def seed_pending_review_scans(db: Session) -> list[Scan]:
    """Seed canonical PENDING_REVIEW scans matching §4.2 sketch:
    - Parle-G 100g (Chennai, TN) ~2h ago
    - Amul Butter 500g (Coimbatore) ~5h ago
    - Maggi Noodles 70g (Madurai) ~1d ago
    - Britannia Good Day 200g (Salem) ~3h ago
    """
    now = datetime.now(timezone.utc)
    scans_created = []

    seed_definitions = [
        {
            "brand": "Parle-G 100g",
            "net_qty": "100g",
            "mrp": "Rs. 10.00",
            "lat": 13.0827,
            "lng": 80.2707,  # Chennai
            "delta_hours": 2,
            "image_url": "test_fixture_parle_g_100g.jpg",
            "evidence_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "ocr_confidences": [0.94, 0.70],  # gap = 0.24 (24%)
        },
        {
            "brand": "Amul Butter 500g",
            "net_qty": "500g",
            "mrp": "Rs. 275.00",
            "lat": 11.0168,
            "lng": 76.9558,  # Coimbatore
            "delta_hours": 5,
            "image_url": "test_fixture_amul_butter_500g.jpg",
            "evidence_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
            "ocr_confidences": [0.98, 0.82],  # gap = 0.16 (16%)
        },
        {
            "brand": "Maggi Noodles 70g",
            "net_qty": "70g",
            "mrp": "Rs. 14.00",
            "lat": 9.9252,
            "lng": 78.1198,  # Madurai
            "delta_hours": 24,
            "image_url": "test_fixture_maggi_noodles_70g.jpg",
            "evidence_hash": "5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9",
            "ocr_confidences": [0.92, 0.61],  # gap = 0.31 (31%)
        },
        {
            "brand": "Britannia Good Day 200g",
            "net_qty": "200g",
            "mrp": "Rs. 45.00",
            "lat": 11.6643,
            "lng": 78.1460,  # Salem
            "delta_hours": 3,
            "image_url": "test_fixture_good_day_200g.jpg",
            "evidence_hash": "6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b",
            "ocr_confidences": [0.96, 0.88],  # gap = 0.08 (8%)
        }
    ]

    for item in seed_definitions:
        created_time = now - timedelta(hours=item["delta_hours"])
        scan = Scan(
            scan_id=uuid.uuid4(),
            source=ScanSource.MOBILE.value,
            status=ScanStatus.PENDING_REVIEW.value,
            image_url=item["image_url"],
            evidence_hash=item["evidence_hash"],
            lat=item["lat"],
            lng=item["lng"],
            captured_at_utc=created_time,
            created_at=created_time,
            mm_per_px=0.085,
            pdp_area_cm2=120.5,
            ruleset_version="2026.1"
        )
        db.add(scan)
        db.flush()

        # Add extracted fields with realistic bounding box coordinates (normalized percentages [x1, y1, x2, y2])
        # Preserves Section 65B chain-of-custody: coordinates rendered as client SVG overlay, NOT burned into raw image
        ef_brand = ExtractedField(
            id=uuid.uuid4(),
            scan_id=scan.scan_id,
            field_name="brand_name",
            raw_text=item["brand"],
            bbox={"x1": 18.5, "y1": 15.0, "x2": 65.0, "y2": 26.5},
            ocr_confidence=item["ocr_confidences"][0],
            semantic_confidence=0.95,
            font_height_mm=4.5
        )
        ef_qty = ExtractedField(
            id=uuid.uuid4(),
            scan_id=scan.scan_id,
            field_name="net_quantity",
            raw_text=item["net_qty"],
            bbox={"x1": 22.0, "y1": 55.0, "x2": 48.0, "y2": 63.0},
            ocr_confidence=item["ocr_confidences"][1],
            semantic_confidence=0.88,
            font_height_mm=2.8
        )
        ef_mrp = ExtractedField(
            id=uuid.uuid4(),
            scan_id=scan.scan_id,
            field_name="mrp",
            raw_text=item["mrp"],
            bbox={"x1": 52.0, "y1": 54.0, "x2": 82.0, "y2": 63.5},
            ocr_confidence=0.91,
            semantic_confidence=0.90,
            font_height_mm=3.0
        )
        ef_mfg = ExtractedField(
            id=uuid.uuid4(),
            scan_id=scan.scan_id,
            field_name="manufacturer_address",
            raw_text="Parle Products Pvt. Ltd., V.S. Khandekar Marg, Vile Parle East, Mumbai 400057",
            bbox={"x1": 15.0, "y1": 70.0, "x2": 85.0, "y2": 82.0},
            ocr_confidence=0.93,
            semantic_confidence=0.91,
            font_height_mm=1.8
        )
        ef_care = ExtractedField(
            id=uuid.uuid4(),
            scan_id=scan.scan_id,
            field_name="consumer_care",
            raw_text="Email: cs@consumer.org | Toll Free: 1800-22-1929",
            bbox={"x1": 15.0, "y1": 84.0, "x2": 78.0, "y2": 92.0},
            ocr_confidence=0.89,
            semantic_confidence=0.92,
            font_height_mm=1.6
        )
        db.add_all([ef_brand, ef_qty, ef_mrp, ef_mfg, ef_care])

        # Add rule results matching §4.3: 6(1)(a), 6(1)(c), 6(1)(e), 6(1)(g), schedule_ii
        rr_a = RuleResult(
            id=uuid.uuid4(),
            scan_id=scan.scan_id,
            rule_id="6.1.a",
            status=RuleStatus.PASS,
            reason="Manufacturer name & complete address verified with valid pin code",
            evidence={"confidence": 0.95, "field": "manufacturer_address"}
        )
        rr_c = RuleResult(
            id=uuid.uuid4(),
            scan_id=scan.scan_id,
            rule_id="6.1.c",
            status=RuleStatus.PASS,
            reason="Standard SI metric units (g/kg/ml) correctly stated",
            evidence={"unit": "g", "declared_qty": item["net_qty"]}
        )
        rr_e = RuleResult(
            id=uuid.uuid4(),
            scan_id=scan.scan_id,
            rule_id="6.1.e",
            status=RuleStatus.FAIL if "Maggi" in item["brand"] else RuleStatus.PASS,
            reason="Missing statutory phrase 'inclusive of all taxes'" if "Maggi" in item["brand"] else "Statutory phrase 'inclusive of all taxes' present and legible",
            evidence={"raw_mrp": item["mrp"], "has_tax_phrase": ("Maggi" not in item["brand"])}
        )
        rr_g = RuleResult(
            id=uuid.uuid4(),
            scan_id=scan.scan_id,
            rule_id="6.1.g",
            status=RuleStatus.PASS,
            reason="Consumer care telephone and email contact provided",
            evidence={"contact_types": ["email", "phone"]}
        )
        rr_sched2 = RuleResult(
            id=uuid.uuid4(),
            scan_id=scan.scan_id,
            rule_id="schedule_ii",
            status=RuleStatus.UNVERIFIED,
            reason="Confidence gap on net quantity numeral height requires senior LMO visual verification",
            evidence={
                "measured_height_mm": 2.8,
                "required_height_mm": 3.0,
                "confidence_gap": item["ocr_confidences"][0] - item["ocr_confidences"][1]
            }
        )
        db.add_all([rr_a, rr_c, rr_e, rr_g, rr_sched2])
        scans_created.append(scan)

    db.commit()
    return scans_created
