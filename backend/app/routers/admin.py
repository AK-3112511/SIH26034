"""§3 Screens 8-9 — Admin: Ruleset Config (Phase 6.3) & User Management (Phase 6.4)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.ruleset_version import RulesetVersion
from app.models.user import User
from app.schemas.audit import AuditLogEntry, AuditLogListResponse
from app.schemas.auth import UserResponse
from app.schemas.ruleset import (
    RulesetVersionCreate,
    RulesetVersionListResponse,
    RulesetVersionResponse,
)
from app.schemas.user_admin import UserCreateRequest, UserListResponse, UserUpdateRequest
from app.services.audit import log_audit
from app.services.rules.ruleset_admin import (
    DuplicateVersionError,
    VersionNotFoundError,
    activate_version,
    create_version,
    list_versions,
)
from app.services.user_admin import (
    DuplicateUserError,
    UserNotFoundError,
    create_user,
    list_users,
    update_user,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _to_response(row: RulesetVersion) -> RulesetVersionResponse:
    return RulesetVersionResponse(
        version=row.version,
        effective_date=row.effective_date,
        is_placeholder=row.is_placeholder,
        notice=row.notice,
        bands=row.bands,
        is_active=row.is_active,
        created_by_id=row.created_by_id,
        created_at=row.created_at,
    )


@router.get("/rulesets", response_model=RulesetVersionListResponse)
def get_rulesets(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> RulesetVersionListResponse:
    rows = list_versions(db)
    return RulesetVersionListResponse(versions=[_to_response(r) for r in rows])


@router.post("/rulesets", response_model=RulesetVersionResponse, status_code=status.HTTP_201_CREATED)
def post_ruleset(
    payload: RulesetVersionCreate,
    activate: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> RulesetVersionResponse:
    try:
        row = create_version(db, payload, created_by_id=current_user.id, activate=activate)
    except DuplicateVersionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    log_audit(
        db=db,
        action="RULESET_VERSION_CREATED",
        target_type="ruleset",
        target_id=row.version,
        actor_id=current_user.id,
        detail={
            "effective_date": row.effective_date.isoformat(),
            "is_placeholder": row.is_placeholder,
            "activated": row.is_active,
            "band_count": len(row.bands),
        },
    )
    db.commit()
    return _to_response(row)


@router.post("/rulesets/{version}/activate", response_model=RulesetVersionResponse)
def post_activate_ruleset(
    version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> RulesetVersionResponse:
    try:
        row = activate_version(db, version)
    except VersionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    log_audit(
        db=db,
        action="RULESET_VERSION_ACTIVATED",
        target_type="ruleset",
        target_id=row.version,
        actor_id=current_user.id,
        detail={"effective_date": row.effective_date.isoformat(), "is_placeholder": row.is_placeholder},
    )
    db.commit()
    return _to_response(row)


# ---------------------------------------------------------------------------
# §3 Screen 9 — Admin: User Management (Phase 6.4)
# ---------------------------------------------------------------------------

@router.get("/users", response_model=UserListResponse)
def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> UserListResponse:
    users = list_users(db)
    return UserListResponse(users=[UserResponse.model_validate(u) for u in users])


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def post_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> UserResponse:
    try:
        user = create_user(db, payload)
    except DuplicateUserError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    log_audit(
        db=db,
        action="USER_CREATED",
        target_type="user",
        target_id=str(user.id),
        actor_id=current_user.id,
        detail={"username": user.username, "role": user.role.value, "district": user.district},
    )
    db.commit()
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
def patch_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> UserResponse:
    try:
        user = update_user(db, user_id, payload)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    log_audit(
        db=db,
        action="USER_UPDATED",
        target_type="user",
        target_id=str(user.id),
        actor_id=current_user.id,
        detail={
            "role": user.role.value,
            "district": user.district,
            "is_active": user.is_active,
        },
    )
    db.commit()
    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# §3 Screen 10 — Audit Log (Phase 6.5). Read-only by design: no edit/delete
# endpoints exist here, matching the append-only audit_log table itself.
# ---------------------------------------------------------------------------

@router.get("/audit-log", response_model=AuditLogListResponse)
def get_audit_log(
    target_type: str | None = Query(None),
    action: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> AuditLogListResponse:
    query = db.query(AuditLog)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)
    if action:
        query = query.filter(AuditLog.action == action)

    total = query.count()
    rows = (
        query.order_by(AuditLog.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        AuditLogEntry(
            id=row.id,
            actor_id=row.actor_id,
            actor_username=row.actor.username if row.actor else None,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            timestamp=row.timestamp,
            detail=row.detail,
        )
        for row in rows
    ]
    return AuditLogListResponse(items=items, total=total, page=page, page_size=page_size)
