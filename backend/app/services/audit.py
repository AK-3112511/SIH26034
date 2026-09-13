import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_audit(
    db: Session,
    action: str,
    target_type: str,
    target_id: str | None = None,
    actor_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None
) -> AuditLog:
    """Record an immutable, append-only entry in the audit_log table.

    Per §12 of the blueprint, every security and status-changing action
    is preserved with actor identity, action type, target entity, timestamp,
    and structured JSON detail.
    """
    entry = AuditLog(
        id=uuid.uuid4(),
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        detail=detail
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def log_status_change(
    db: Session,
    target_type: str,
    target_id: str,
    new_status: str,
    old_status: str | None = None,
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    detail: dict[str, Any] | None = None
) -> AuditLog:
    """Automated helper to record status transitions on managed entities (e.g. Scans, Challans)."""
    payload = {
        "old_status": str(old_status) if old_status is not None else None,
        "new_status": str(new_status)
    }
    if detail:
        payload.update(detail)

    action_name = action or f"{target_type.upper()}_STATUS_{new_status}"
    return log_audit(
        db=db,
        action=action_name,
        target_type=target_type,
        target_id=target_id,
        actor_id=actor_id,
        detail=payload
    )


# Backward-compatibility alias
def log_audit_event(
    db: Session,
    action: str,
    entity_type: str,
    actor_id: uuid.UUID | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None
) -> AuditLog:
    """Compatibility alias mapping old signature to log_audit."""
    return log_audit(
        db=db,
        action=action,
        target_type=entity_type,
        target_id=entity_id,
        actor_id=actor_id,
        detail=details
    )
