from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class RuleResultSummary(BaseModel):
    rule_id: str
    status: str
    reason: Optional[str] = None


class ScanStatusChangedPayload(BaseModel):
    scan_id: str
    new_status: str
    rule_results: List[RuleResultSummary] = Field(default_factory=list)
    assigned_lmo_id: Optional[str] = None


class TaskAssignedPayload(BaseModel):
    scan_id: str
    assigned_to_lmo_id: str
    task_type: str = "field_followup"


class EventItem(BaseModel):
    id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class PollEventsResponse(BaseModel):
    events: List[EventItem]
    count: int
    server_time: datetime


class AssignTaskRequest(BaseModel):
    scan_id: uuid.UUID
    assigned_to_lmo_id: uuid.UUID
    task_type: str = "field_followup"


class AssignTaskResponse(BaseModel):
    scan_id: uuid.UUID
    assigned_to_lmo_id: uuid.UUID
    task_type: str
    message: str
