"""Phase 7.1: Real-time event polling and assignment router per §6.2."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin, require_senior_lmo
from app.db.session import get_db
from app.models.scan import Scan
from app.models.user import User
from app.schemas.events import (
    AssignTaskRequest,
    AssignTaskResponse,
    EventItem,
    PollEventsResponse,
)
from app.services.audit import log_audit
from app.services.events import (
    cleanup_expired_events,
    emit_task_assigned,
    get_events_for_user,
)

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/poll", response_model=PollEventsResponse)
def poll_events(
    since: Optional[str] = Query(
        None,
        description="ISO 8601 timestamp cutoff (e.g. 2026-09-21T10:00:00Z). Returns events created strictly after this time.",
    ),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve new events for the authenticated client since last poll timestamp.
    
    Implements §6.2 polling update layer:
    - Field LMOs receive scan.status_changed for their scans and task.assigned tasks.
    - Senior LMOs and Admins receive scan.status_changed queue updates for their district.
    """
    parsed_since: Optional[datetime] = None
    if since and since.strip():
        raw = since.strip()
        # Handle unencoded plus in timezone offset replaced by space by HTTP decoders
        if " " in raw and "+" not in raw:
            raw = raw.replace(" ", "+")
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed_since = datetime.fromisoformat(raw)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid ISO 8601 timestamp format for 'since': '{since}'",
            )

    # Opportunistic pruning of events older than 7 days
    try:
        cleanup_expired_events(db)
    except Exception:
        # Pruning failure must never block event delivery
        pass

    events = get_events_for_user(db=db, current_user=current_user, since=parsed_since, limit=limit)

    return PollEventsResponse(
        events=[
            EventItem(
                id=e.id,
                event_type=e.event_type,
                payload=e.payload,
                created_at=e.created_at,
            )
            for e in events
        ],
        count=len(events),
        server_time=datetime.now(timezone.utc),
    )


@router.post("/task-assigned", response_model=AssignTaskResponse, status_code=status.HTTP_200_OK)
def assign_scan_task(
    body: AssignTaskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_senior_lmo),
):
    """Assign a scan to a field LMO for field follow-up per §5.3 & §6.2.
    
    Emits task.assigned event:
      payload: { scan_id, assigned_to_lmo_id, task_type: 'field_followup' }
      -> pushed to assigned_to_lmo_id (mobile Home screen new item)
    """
    # Verify target field LMO exists
    target_lmo = db.query(User).filter(User.id == body.assigned_to_lmo_id).first()
    if not target_lmo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target officer with ID '{body.assigned_to_lmo_id}' not found",
        )

    # Verify scan exists
    scan = db.query(Scan).filter(Scan.scan_id == body.scan_id).first()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan with ID '{body.scan_id}' not found",
        )

    # Assign scan to field officer
    scan.assigned_lmo_id = body.assigned_to_lmo_id
    db.commit()
    db.refresh(scan)

    # Log audit entry
    log_audit(
        db=db,
        action="TASK_ASSIGNED",
        target_type="scan",
        target_id=str(scan.scan_id),
        actor_id=current_user.id,
        detail={
            "assigned_to_lmo_id": str(body.assigned_to_lmo_id),
            "task_type": body.task_type,
            "assigned_by": str(current_user.id),
        },
    )

    # Emit task.assigned event per §6.2
    emit_task_assigned(
        db=db,
        scan_id=scan.scan_id,
        assigned_to_lmo_id=body.assigned_to_lmo_id,
        task_type=body.task_type,
    )

    return AssignTaskResponse(
        scan_id=scan.scan_id,
        assigned_to_lmo_id=body.assigned_to_lmo_id,
        task_type=body.task_type,
        message=f"Task successfully assigned to officer {target_lmo.full_name}",
    )


@router.post("/prune", status_code=status.HTTP_200_OK)
def prune_expired_events(
    retention_days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Explicitly trigger retention cleanup for events older than retention_days (admin only)."""
    deleted = cleanup_expired_events(db=db, retention_days=retention_days)
    return {
        "status": "ok",
        "deleted_count": deleted,
        "retention_days": retention_days,
        "timestamp": datetime.now(timezone.utc),
    }
