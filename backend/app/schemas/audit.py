"""§3 Screen 10 — read-only Audit Log contract."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_username: str | None
    action: str
    target_type: str
    target_id: str | None
    timestamp: datetime
    detail: dict[str, Any] | None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int
