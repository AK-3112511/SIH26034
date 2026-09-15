"""§10 GET /api/v1/dashboard/heatmap — aggregated GIS points for map rendering."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import require_senior_lmo
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import HeatmapResponse
from app.services.geo.heatmap_service import (
    DEFAULT_ZOOM,
    MAX_ZOOM,
    MIN_ZOOM,
    compute_heatmap_clusters,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if bbox is None:
        return None
    parts = bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(
            status_code=422,
            detail="bbox must be 'min_lat,min_lng,max_lat,max_lng'",
        )
    try:
        min_lat, min_lng, max_lat, max_lng = (float(p) for p in parts)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="bbox must be 'min_lat,min_lng,max_lat,max_lng'",
        ) from exc
    return (min_lat, min_lng, max_lat, max_lng)


@router.get("/heatmap", response_model=HeatmapResponse)
def get_heatmap(
    zoom: int = Query(DEFAULT_ZOOM, ge=MIN_ZOOM, le=MAX_ZOOM, description="Map zoom driving cluster cell size"),
    bbox: str | None = Query(
        None, description="Viewport filter: 'min_lat,min_lng,max_lat,max_lng'"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_senior_lmo),
) -> HeatmapResponse:
    parsed_bbox = _parse_bbox(bbox)
    clusters = compute_heatmap_clusters(db, zoom=zoom, bbox=parsed_bbox)
    total_points = sum(c["count"] for c in clusters)
    return HeatmapResponse(clusters=clusters, zoom=zoom, total_points=total_points)
