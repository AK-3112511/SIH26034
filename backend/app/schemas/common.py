"""Shared Pydantic helpers."""
from __future__ import annotations

from typing import Annotated

from pydantic import PlainSerializer

from app.services.files import sign_file_url

# A stored evidence key that is rendered as a signed, time-limited /files URL.
SignedFileUrl = Annotated[str, PlainSerializer(lambda v: sign_file_url(v), return_type=str)]
OptionalSignedFileUrl = Annotated[str | None, PlainSerializer(lambda v: sign_file_url(v), return_type=str | None)]
