"""Validation for uploaded evidence images.

Content is sniffed from the bytes themselves — the client-declared
``Content-Type`` is not trusted.
"""
from __future__ import annotations

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"RIFF", "image/webp", ".webp"),  # RIFF....WEBP, checked below
)


def sniff_image_type(data: bytes) -> tuple[str, str] | None:
    """Return ``(media_type, extension)`` for supported image bytes, else ``None``."""
    for magic, media_type, ext in _SIGNATURES:
        if data.startswith(magic):
            if media_type == "image/webp" and data[8:12] != b"WEBP":
                return None
            return media_type, ext
    return None


async def read_validated_image(image: UploadFile) -> tuple[bytes, str, str]:
    """Read an upload, enforce size/type limits and return ``(bytes, media_type, filename)``."""
    limit = settings.MAX_UPLOAD_BYTES
    data = await image.read(limit + 1)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded image file is empty")
    if len(data) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the {limit // (1024 * 1024)} MB upload limit",
        )
    sniffed = sniff_image_type(data)
    if sniffed is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported image format — upload a JPEG, PNG or WebP photo",
        )
    media_type, ext = sniffed
    base = (image.filename or "capture").rsplit(".", 1)[0] or "capture"
    return data, media_type, f"{base}{ext}"
