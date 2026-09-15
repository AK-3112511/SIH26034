"""§10 GET /api/v1/dashboard/heatmap response contract."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HeatmapCluster(BaseModel):
    lat: float
    lng: float
    count: int
    severity: Literal["FAIL", "PENDING", "PASS"]
    pass_count: int
    fail_count: int
    pending_count: int


class HeatmapResponse(BaseModel):
    clusters: list[HeatmapCluster]
    zoom: int
    total_points: int
