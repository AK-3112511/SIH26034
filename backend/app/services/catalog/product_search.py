"""§10 GET /api/v1/products/search — Digital Repository lookup by brand/barcode.

Data-model honesty note: the Phase 3.2 extraction schema (net_quantity, mrp,
mfg_date, manufacturer_name, manufacturer_address, pincode, consumer_care,
unit) never defined a dedicated `brand` or `barcode` field. Packaging OCR
doesn't reliably surface a GTIN/barcode value, and "brand" (e.g. "Parle-G")
is conceptually different from "manufacturer" (e.g. "Parle Products Pvt
Ltd"). Rather than fabricate a barcode field with nothing real behind it,
product identity here is grouped by `manufacturer_name` — the closest field
that actually exists and is actually extracted by the pipeline. This is
flagged in /audit/progress.md as an open item: a real barcode/brand field
needs to be added to the extraction schema before "search by barcode" as
literally described in the blueprint is meaningful.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.enums import ScanStatus
from app.models.scan import Scan

MAX_SCANS_PER_PRODUCT = 100
# Minimum pass-rate swing between the older and newer half of a product's
# decided scans before it's called a trend rather than noise.
TREND_THRESHOLD = 0.1


def _manufacturer_name(scan: Scan) -> str | None:
    for ef in scan.extracted_fields:
        if ef.field_name == "manufacturer_name" and ef.raw_text and ef.raw_text.strip():
            return ef.raw_text.strip()
    return None


def _scan_timestamp(scan: Scan) -> datetime:
    return scan.captured_at_utc or scan.created_at


def _compute_trend(scans_oldest_first: list[Scan]) -> tuple[str, float | None]:
    """Trend + overall pass rate among *decided* scans (PASSED/FAILED only)."""
    decided = [s for s in scans_oldest_first if s.status in (ScanStatus.PASSED, ScanStatus.FAILED)]
    if not decided:
        return "INSUFFICIENT_DATA", None

    overall_rate = sum(1 for s in decided if s.status == ScanStatus.PASSED) / len(decided)
    if len(decided) < 2:
        return "INSUFFICIENT_DATA", overall_rate

    mid = len(decided) // 2
    older, newer = decided[:mid], decided[mid:]
    if not older or not newer:
        return "INSUFFICIENT_DATA", overall_rate

    older_rate = sum(1 for s in older if s.status == ScanStatus.PASSED) / len(older)
    newer_rate = sum(1 for s in newer if s.status == ScanStatus.PASSED) / len(newer)
    delta = newer_rate - older_rate

    if delta > TREND_THRESHOLD:
        return "IMPROVING", overall_rate
    if delta < -TREND_THRESHOLD:
        return "WORSENING", overall_rate
    return "STABLE", overall_rate


def search_products(
    db: Session, query: str | None, page: int, page_size: int
) -> tuple[list[dict], int]:
    """Group scans by manufacturer_name, filter by `query`, return one page.

    Returns (page_of_product_dicts, total_matching_products).
    """
    all_scans = db.query(Scan).all()

    groups: dict[str, list[Scan]] = defaultdict(list)
    for scan in all_scans:
        name = _manufacturer_name(scan)
        if name is not None:
            groups[name].append(scan)

    if query:
        needle = query.strip().lower()
        groups = {name: scans for name, scans in groups.items() if needle in name.lower()}

    products: list[dict] = []
    for name, scans in groups.items():
        newest_first = sorted(scans, key=_scan_timestamp, reverse=True)
        oldest_first = list(reversed(newest_first))

        passed = sum(1 for s in scans if s.status == ScanStatus.PASSED)
        failed = sum(1 for s in scans if s.status == ScanStatus.FAILED)
        pending = sum(1 for s in scans if s.status == ScanStatus.PENDING_REVIEW)
        other = len(scans) - passed - failed - pending

        trend, pass_rate = _compute_trend(oldest_first)

        products.append(
            {
                "manufacturer_name": name,
                "total_scans": len(scans),
                "passed_count": passed,
                "failed_count": failed,
                "pending_review_count": pending,
                "other_count": other,
                "pass_rate": pass_rate,
                "trend": trend,
                "first_scan_at": _scan_timestamp(oldest_first[0]),
                "last_scan_at": _scan_timestamp(newest_first[0]),
                "scans": newest_first[:MAX_SCANS_PER_PRODUCT],
            }
        )

    # Most recently active products surface first.
    products.sort(key=lambda p: p["last_scan_at"], reverse=True)

    total = len(products)
    start = (page - 1) * page_size
    end = start + page_size
    return products[start:end], total
