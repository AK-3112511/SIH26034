"""§10 GET /api/v1/products/search response contract."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import SignedFileUrl


class ProductScanEntry(BaseModel):
    scan_id: uuid.UUID
    status: str
    district_label: str | None
    captured_at_utc: datetime | None
    created_at: datetime
    image_url: SignedFileUrl


class ProductSearchResult(BaseModel):
    manufacturer_name: str
    total_scans: int
    passed_count: int
    failed_count: int
    pending_review_count: int
    other_count: int
    pass_rate: float | None
    trend: Literal["IMPROVING", "WORSENING", "STABLE", "INSUFFICIENT_DATA"]
    first_scan_at: datetime
    last_scan_at: datetime
    scans: list[ProductScanEntry]


class ProductSearchResponse(BaseModel):
    query: str | None
    results: list[ProductSearchResult]
    total: int
    page: int
    page_size: int
