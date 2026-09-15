"""§10 GET /api/v1/products/search — Digital Repository / Product Search (Phase 6.2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_senior_lmo
from app.db.session import get_db
from app.models.user import User
from app.schemas.product import ProductScanEntry, ProductSearchResponse, ProductSearchResult
from app.services.catalog.product_search import search_products
from app.services.district import resolve_district_label

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/search", response_model=ProductSearchResponse)
def search_products_endpoint(
    query: str | None = Query(
        None, alias="q", description="Brand/manufacturer name substring (see module docstring re: barcode)"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_senior_lmo),
) -> ProductSearchResponse:
    page_items, total = search_products(db, query, page=page, page_size=page_size)

    results = [
        ProductSearchResult(
            manufacturer_name=item["manufacturer_name"],
            total_scans=item["total_scans"],
            passed_count=item["passed_count"],
            failed_count=item["failed_count"],
            pending_review_count=item["pending_review_count"],
            other_count=item["other_count"],
            pass_rate=item["pass_rate"],
            trend=item["trend"],
            first_scan_at=item["first_scan_at"],
            last_scan_at=item["last_scan_at"],
            scans=[
                ProductScanEntry(
                    scan_id=s.scan_id,
                    status=s.status.value if hasattr(s.status, "value") else s.status,
                    district_label=resolve_district_label(s, db),
                    captured_at_utc=s.captured_at_utc,
                    created_at=s.created_at,
                    image_url=s.image_url,
                )
                for s in item["scans"]
            ],
        )
        for item in page_items
    ]

    return ProductSearchResponse(query=query, results=results, total=total, page=page, page_size=page_size)
