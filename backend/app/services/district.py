"""Best-effort district-label resolution, shared by the Review Queue list
(Phase 4.3) and Product Search timeline (Phase 6.2) so the heuristic lives
in exactly one place.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.scan import Scan
from app.models.user import User


def resolve_district_label(scan: Scan, db: Session | None = None) -> str | None:
    """Resolve human-readable district label from assigned officer or GPS coordinates."""
    if scan.assigned_lmo_id and db:
        user = db.query(User).filter(User.id == scan.assigned_lmo_id).first()
        if user and user.district:
            return user.district

    if scan.lat is not None and scan.lng is not None:
        lat, lng = scan.lat, scan.lng
        if 12.8 <= lat <= 13.4 and 79.8 <= lng <= 80.5:
            return "Chennai, TN"
        elif 10.7 <= lat <= 11.4 and 76.7 <= lng <= 77.4:
            return "Coimbatore, TN"
        elif 9.6 <= lat <= 10.2 and 77.8 <= lng <= 78.4:
            return "Madurai, TN"
        elif 11.4 <= lat <= 11.9 and 77.9 <= lng <= 78.4:
            return "Salem, TN"
        return f"{lat:.2f}N, {lng:.2f}E"

    return None
