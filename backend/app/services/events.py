"""Phase 7.1: Real-time event dispatch and retention service per §6.2."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from app.models.event import EventLog
from app.models.user import User

logger = logging.getLogger(__name__)

EVENT_SCAN_STATUS_CHANGED = "scan.status_changed"
EVENT_TASK_ASSIGNED = "task.assigned"

DEFAULT_RETENTION_DAYS = 7


def dispatch_event(
    db: Session,
    event_type: str,
    payload: dict[str, Any],
    target_user_id: Optional[uuid.UUID] = None,
    target_district: Optional[str] = None,
    target_role: Optional[str] = None,
) -> EventLog:
    """Persist an event to the event_logs table for client polling delivery."""
    event = EventLog(
        id=uuid.uuid4(),
        event_type=event_type,
        payload=payload,
        target_user_id=target_user_id,
        target_district=target_district,
        target_role=target_role,
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    logger.info("Dispatched event %s (id=%s) -> target_user=%s, district=%s", event_type, event.id, target_user_id, target_district)
    return event


def emit_scan_status_changed(
    db: Session,
    scan_id: uuid.UUID | str,
    new_status: str,
    rule_results: Optional[List[dict[str, Any]]] = None,
    assigned_lmo_id: Optional[uuid.UUID | str] = None,
    district: Optional[str] = None,
) -> EventLog:
    """Emit scan.status_changed event per §6.2.
    
    Payload: { scan_id, new_status, rule_results[], assigned_lmo_id }
    - Pushed to assigned_lmo_id (mobile notification for field officer)
    - Pushed to all senior_lmo / admin dashboard sessions in that district (queue update)
    """
    cleaned_rule_results: List[dict[str, Any]] = []
    if rule_results:
        for r in rule_results:
            if isinstance(r, dict):
                cleaned_rule_results.append({
                    "rule_id": str(r.get("rule_id", "")),
                    "status": str(r.get("status", "")),
                    "reason": r.get("reason"),
                })

    assigned_id_str = str(assigned_lmo_id) if assigned_lmo_id else None
    assigned_uuid = uuid.UUID(assigned_id_str) if assigned_id_str else None

    payload = {
        "scan_id": str(scan_id),
        "new_status": str(new_status),
        "rule_results": cleaned_rule_results,
        "assigned_lmo_id": assigned_id_str,
    }

    return dispatch_event(
        db=db,
        event_type=EVENT_SCAN_STATUS_CHANGED,
        payload=payload,
        target_user_id=assigned_uuid,
        target_district=district,
        target_role=None,  # Handled by district/role routing query
    )


def emit_task_assigned(
    db: Session,
    scan_id: uuid.UUID | str,
    assigned_to_lmo_id: uuid.UUID | str,
    task_type: str = "field_followup",
) -> EventLog:
    """Emit task.assigned event per §6.2.
    
    Payload: { scan_id, assigned_to_lmo_id, task_type: 'field_followup' }
    - Pushed to assigned_to_lmo_id (mobile Home screen new item)
    """
    assigned_id_str = str(assigned_to_lmo_id)
    assigned_uuid = uuid.UUID(assigned_id_str)

    payload = {
        "scan_id": str(scan_id),
        "assigned_to_lmo_id": assigned_id_str,
        "task_type": task_type,
    }

    return dispatch_event(
        db=db,
        event_type=EVENT_TASK_ASSIGNED,
        payload=payload,
        target_user_id=assigned_uuid,
        target_district=None,
        target_role="field_lmo",
    )


def get_events_for_user(
    db: Session,
    current_user: User,
    since: Optional[datetime] = None,
    limit: int = 50,
) -> List[EventLog]:
    """Retrieve pending/historical events visible to current_user since given timestamp.
    
    Matches:
    1. Personal events where target_user_id == current_user.id
    2. District events for senior_lmo/admin where target_district matches user's district
    3. Global broadcast events where target_user_id, target_district, and target_role are null
    """
    conditions = [
        EventLog.target_user_id == current_user.id,
    ]

    # Senior LMOs and Admins receive district-wide updates for review queues
    if current_user.role.value in ("senior_lmo", "admin"):
        if current_user.district:
            conditions.append(
                and_(
                    func.lower(EventLog.target_district) == current_user.district.lower(),
                    or_(EventLog.target_role.is_(None), EventLog.target_role.in_(["senior_lmo", "admin"])),
                )
            )
        else:
            # District-less admin sees all district events
            conditions.append(
                or_(EventLog.target_role.is_(None), EventLog.target_role.in_(["senior_lmo", "admin"]))
            )

    # General broadcast events
    conditions.append(
        and_(
            EventLog.target_user_id.is_(None),
            EventLog.target_district.is_(None),
            or_(EventLog.target_role.is_(None), EventLog.target_role == current_user.role.value),
        )
    )

    query = db.query(EventLog).filter(or_(*conditions))

    if since:
        query = query.filter(EventLog.created_at > since)

    return query.order_by(EventLog.created_at.asc()).limit(limit).all()


def cleanup_expired_events(db: Session, retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
    """Prune event_logs rows older than retention window (default 7 days).
    
    Returns the number of deleted rows.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted_count = (
        db.query(EventLog)
        .filter(EventLog.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    if deleted_count > 0:
        db.commit()
        logger.info("Cleaned up %d expired event_logs older than %s", deleted_count, cutoff)
    return deleted_count
