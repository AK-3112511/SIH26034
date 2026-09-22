"""Evidence file access.

Scan images and challan PDFs are legal evidence, so they are never exposed
through a public static mount.  Stored records keep a *storage key*; API
responses convert that key into a short-lived signed URL

    /api/v1/files/{key}?exp=<unix>&sig=<hmac>

which browsers can load in ``<img>``/``<a>`` tags without custom headers.  The
same endpoint also accepts a normal bearer token.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from urllib.parse import urlencode

from app.core.config import settings

_LEGACY_PREFIX = "/static/uploads/"
_FILES_PATH = "/files/"


def storage_key(stored_value: str) -> str:
    """Normalise whatever is persisted on a record into a bare storage key.

    Accepts bare keys, the legacy ``/static/uploads/<key>`` form and already
    signed ``/api/v1/files/<key>?...`` URLs.  Absolute URLs (S3) are returned
    unchanged.
    """
    if stored_value.startswith(("http://", "https://")):
        return stored_value
    value = stored_value.split("?", 1)[0]
    value = value.removeprefix(_LEGACY_PREFIX)
    marker = f"{settings.API_V1_STR}{_FILES_PATH}"
    value = value.removeprefix(marker)
    return os.path.basename(value)


def _signature(key: str, exp: int) -> str:
    message = f"{key}:{exp}".encode()
    return hmac.new(settings.JWT_SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()[:40]


def sign_file_url(stored_value: str | None, ttl_seconds: int | None = None) -> str | None:
    """Return a signed, time-limited URL for a stored file key."""
    if not stored_value:
        return stored_value
    if stored_value.startswith(("http://", "https://")):
        return stored_value
    key = storage_key(stored_value)
    exp = int(time.time()) + (ttl_seconds or settings.FILE_URL_TTL_SECONDS)
    query = urlencode({"exp": exp, "sig": _signature(key, exp)})
    return f"{settings.API_V1_STR}{_FILES_PATH}{key}?{query}"


def verify_file_signature(key: str, exp: int | None, sig: str | None) -> bool:
    if exp is None or not sig:
        return False
    if exp < int(time.time()):
        return False
    return hmac.compare_digest(_signature(key, exp), sig)


def guess_media_type(key: str) -> str:
    lower = key.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"
