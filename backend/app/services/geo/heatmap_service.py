"""§7.1 GIS heatmap aggregation.

Implementation note from the blueprint: "the heatmap is a PostGIS
ST_ClusterKMeans or ST_SnapToGrid aggregation query run server-side (not
client-side clustering of raw points), because plotting millions of raw GPS
points in-browser doesn't scale ... the map tile layer requests
pre-aggregated cluster counts per zoom level."

Dual-engine, matching the pattern used throughout this backend (YOLOv8 /
geometric CV, PaddleOCR / deterministic OCR, etc.):
  - Engine A: real PostGIS ST_SnapToGrid grid aggregation (production/Postgres).
  - Engine B: deterministic Python grid-snap fallback over the plain lat/lng
    columns, used automatically when the bound database is not PostGIS
    (e.g. the SQLite test harness), so this endpoint is unit-testable
    without a live PostGIS instance.
Both engines snap to the same cell size for a given zoom, so cluster counts
are equivalent between the two.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.scan import Scan

MIN_ZOOM = 0
MAX_ZOOM = 20
DEFAULT_ZOOM = 5

_PASS_STATUSES = {"PASSED"}
_FAIL_STATUSES = {"FAILED", "CALIBRATION_FAILED", "LOW_CONFIDENCE_CALIBRATION"}
_PENDING_STATUSES = {"PENDING_REVIEW", "QUEUED"}

BBox = tuple[float, float, float, float]  # (min_lat, min_lng, max_lat, max_lng)


def grid_cell_size_degrees(zoom: int) -> float:
    """Aggregation cell size in degrees for a given map zoom level.

    Illustrative sizing (not a geodetic commitment, per the blueprint's own
    convention for sizing notes): halves per zoom level so the client gets
    few, large clusters zoomed out (national view) and many, small clusters
    zoomed in (district/street view).
    """
    zoom = max(MIN_ZOOM, min(zoom, MAX_ZOOM))
    return 40.0 / (2**zoom)


@dataclass
class _ClusterRow:
    lat: float
    lng: float
    count: int
    pass_count: int
    fail_count: int
    pending_count: int


def _severity(pass_count: int, fail_count: int, pending_count: int) -> str:
    """Dominant verdict in a cell. Ties favor surfacing risk: FAIL > PENDING > PASS."""
    if fail_count >= pass_count and fail_count >= pending_count:
        return "FAIL"
    if pending_count >= pass_count:
        return "PENDING"
    return "PASS"


def _is_postgis(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def _postgis_clusters(db: Session, cell_size: float, bbox: BBox | None) -> list[_ClusterRow]:
    where = ["location IS NOT NULL", "status IS NOT NULL"]
    params: dict[str, float] = {"cell_size": cell_size}
    if bbox is not None:
        min_lat, min_lng, max_lat, max_lng = bbox
        where.append(
            "location && ST_MakeEnvelope(:min_lng, :min_lat, :max_lng, :max_lat, 4326)"
        )
        params.update(min_lat=min_lat, min_lng=min_lng, max_lat=max_lat, max_lng=max_lng)

    sql = text(
        f"""
        SELECT
            ST_Y(ST_Centroid(ST_Collect(location))) AS lat,
            ST_X(ST_Centroid(ST_Collect(location))) AS lng,
            COUNT(*) AS count,
            SUM(CASE WHEN status = 'PASSED' THEN 1 ELSE 0 END) AS pass_count,
            SUM(CASE WHEN status IN ('FAILED','CALIBRATION_FAILED','LOW_CONFIDENCE_CALIBRATION')
                THEN 1 ELSE 0 END) AS fail_count,
            SUM(CASE WHEN status IN ('PENDING_REVIEW','QUEUED') THEN 1 ELSE 0 END) AS pending_count
        FROM scans
        WHERE {" AND ".join(where)}
        GROUP BY ST_SnapToGrid(location, :cell_size)
        """
    )
    rows = db.execute(sql, params).mappings().all()
    return [
        _ClusterRow(
            lat=float(row["lat"]),
            lng=float(row["lng"]),
            count=int(row["count"]),
            pass_count=int(row["pass_count"] or 0),
            fail_count=int(row["fail_count"] or 0),
            pending_count=int(row["pending_count"] or 0),
        )
        for row in rows
    ]


def _python_grid_clusters(db: Session, cell_size: float, bbox: BBox | None) -> list[_ClusterRow]:
    query = db.query(Scan.lat, Scan.lng, Scan.status).filter(
        Scan.lat.isnot(None), Scan.lng.isnot(None)
    )
    if bbox is not None:
        min_lat, min_lng, max_lat, max_lng = bbox
        query = query.filter(
            Scan.lat >= min_lat,
            Scan.lat <= max_lat,
            Scan.lng >= min_lng,
            Scan.lng <= max_lng,
        )

    buckets: dict[tuple[int, int], list[tuple[float, float, str]]] = {}
    for lat, lng, status in query.all():
        status_value = status.value if hasattr(status, "value") else status
        key = (math.floor(lat / cell_size), math.floor(lng / cell_size))
        buckets.setdefault(key, []).append((lat, lng, status_value))

    clusters: list[_ClusterRow] = []
    for points in buckets.values():
        count = len(points)
        avg_lat = sum(p[0] for p in points) / count
        avg_lng = sum(p[1] for p in points) / count
        pass_count = sum(1 for p in points if p[2] in _PASS_STATUSES)
        fail_count = sum(1 for p in points if p[2] in _FAIL_STATUSES)
        pending_count = sum(1 for p in points if p[2] in _PENDING_STATUSES)
        clusters.append(_ClusterRow(avg_lat, avg_lng, count, pass_count, fail_count, pending_count))
    return clusters


def compute_heatmap_clusters(
    db: Session, zoom: int = DEFAULT_ZOOM, bbox: BBox | None = None
) -> list[dict]:
    """Server-side clustered heatmap points — never raw unclustered scans."""
    cell_size = grid_cell_size_degrees(zoom)
    rows = _postgis_clusters(db, cell_size, bbox) if _is_postgis(db) else _python_grid_clusters(
        db, cell_size, bbox
    )
    return [
        {
            "lat": r.lat,
            "lng": r.lng,
            "count": r.count,
            "pass_count": r.pass_count,
            "fail_count": r.fail_count,
            "pending_count": r.pending_count,
            "severity": _severity(r.pass_count, r.fail_count, r.pending_count),
        }
        for r in rows
    ]
