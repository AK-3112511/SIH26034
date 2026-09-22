"""District resolution shared by the queue, product search, events and challans.

The district of a scan is, in order of trust:

1. the district of the officer who captured it (their posting);
2. the district of the officer it was assigned to;
3. a coarse reverse-geocode of the GPS fix against known city bounding boxes;
4. the raw coordinates.

``normalise_district`` gives the canonical comparison key so that
"Chennai, TN", "chennai" and "Chennai " all route to the same officers.
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models.scan import Scan
from app.models.user import User

# (min_lat, max_lat, min_lng, max_lng, label)
_CITY_BOXES: tuple[tuple[float, float, float, float, str], ...] = (
    (12.8, 13.4, 79.8, 80.5, "Chennai, TN"),
    (10.7, 11.4, 76.7, 77.4, "Coimbatore, TN"),
    (9.6, 10.2, 77.8, 78.4, "Madurai, TN"),
    (11.4, 11.9, 77.9, 78.4, "Salem, TN"),
    (12.8, 13.2, 77.3, 77.9, "Bengaluru, KA"),
    (18.8, 19.3, 72.7, 73.1, "Mumbai, MH"),
    (18.4, 18.7, 73.7, 74.0, "Pune, MH"),
    (28.4, 28.9, 76.8, 77.4, "Delhi, DL"),
    (22.4, 22.7, 88.2, 88.5, "Kolkata, WB"),
    (17.2, 17.6, 78.2, 78.7, "Hyderabad, TS"),
    (23.0, 23.2, 72.4, 72.8, "Ahmedabad, GJ"),
    (26.7, 27.0, 75.6, 76.0, "Jaipur, RJ"),
    (28.3, 28.6, 76.9, 77.2, "Gurugram, HR"),
)


def normalise_district(value: str | None) -> str | None:
    """Canonical comparison key: lowercase city name without the state suffix."""
    if not value:
        return None
    key = value.strip().lower()
    key = re.split(r"[,(/]", key, maxsplit=1)[0].strip()
    return key or None


def district_from_coordinates(lat: float | None, lng: float | None) -> str | None:
    if lat is None or lng is None:
        return None
    for min_lat, max_lat, min_lng, max_lng, label in _CITY_BOXES:
        if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
            return label
    return f"{lat:.2f}N, {lng:.2f}E"


def resolve_district_label(scan: Scan, db: Session | None = None, users: dict | None = None) -> str | None:
    """Resolve the human-readable district for a scan.

    ``users`` may be a pre-loaded ``{user_id: User}`` map to avoid a query per scan.
    """
    for officer_id in (scan.captured_by_id, scan.assigned_lmo_id):
        if not officer_id:
            continue
        user = None
        if users is not None:
            user = users.get(officer_id)
        elif db is not None:
            user = db.query(User).filter(User.id == officer_id).first()
        if user and user.district:
            return user.district
    return district_from_coordinates(scan.lat, scan.lng)


def known_districts(db: Session) -> list[str]:
    """Districts officers are posted to plus the city labels the geocoder can emit."""
    by_key: dict[str, str] = {}
    # Geocoder labels first, then officer postings override so the list shows
    # the department's own spelling for a district.
    for *_, label in _CITY_BOXES:
        by_key[normalise_district(label) or label] = label
    for (district,) in db.query(User.district).filter(User.district.isnot(None)).distinct():
        if district and district.strip():
            by_key[normalise_district(district) or district] = district.strip()
    return sorted(by_key.values(), key=lambda v: v.lower())
