import hashlib
from datetime import datetime
from typing import Optional

def compute_section_65b_hash(
    image_bytes: bytes,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    captured_at_utc: Optional[datetime] = None,
    device_id: Optional[str] = None
) -> str:
    """Compute legal Section 65B SHA-256 cryptographic binding over evidentiary capture.

    Per §6.2 of the blueprint, the hash binds the raw untouched image bytes,
    GPS coordinates (lat/lng), UTC timestamp, and capture device ID in an immutable canonical format.
    """
    lat_str = str(lat) if lat is not None else ""
    lng_str = str(lng) if lng is not None else ""
    ts_str = captured_at_utc.isoformat() if captured_at_utc is not None else ""
    dev_str = str(device_id) if device_id is not None else ""

    canonical_payload = (
        image_bytes
        + b"|" + lat_str.encode("utf-8")
        + b"|" + lng_str.encode("utf-8")
        + b"|" + ts_str.encode("utf-8")
        + b"|" + dev_str.encode("utf-8")
    )
    return hashlib.sha256(canonical_payload).hexdigest()


def verify_section_65b_hash(
    expected_hash: str,
    image_bytes: bytes,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    captured_at_utc: Optional[datetime] = None,
    device_id: Optional[str] = None
) -> bool:
    """Verify digital evidence integrity under Section 65B."""
    computed = compute_section_65b_hash(
        image_bytes=image_bytes,
        lat=lat,
        lng=lng,
        captured_at_utc=captured_at_utc,
        device_id=device_id
    )
    return computed == expected_hash
