"""Phase 6.3 admin CRUD over the persisted `ruleset_versions` table.

Append-only by design: this module never updates `bands`/`effective_date`/
`notice` on an existing row — only inserts new rows (`create_version`) and
toggles which single row is `is_active` (`activate_version`). That is what
makes "a version a past challan referenced is never overwritten" true by
construction rather than by a runtime check.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.ruleset_version import RulesetVersion
from app.schemas.ruleset import RulesetVersionCreate


class DuplicateVersionError(Exception):
    """Raised when a version name already exists — must Save as new version instead."""


class VersionNotFoundError(Exception):
    """Raised when activating a version name that doesn't exist."""


def list_versions(db: Session) -> list[RulesetVersion]:
    return db.query(RulesetVersion).order_by(RulesetVersion.created_at.desc()).all()


def create_version(
    db: Session,
    payload: RulesetVersionCreate,
    created_by_id: uuid.UUID | None,
    activate: bool = False,
) -> RulesetVersion:
    existing = db.query(RulesetVersion).filter(RulesetVersion.version == payload.version).first()
    if existing is not None:
        raise DuplicateVersionError(
            f"Ruleset version '{payload.version}' already exists — "
            "save as a new version instead of reusing an existing name"
        )

    row = RulesetVersion(
        version=payload.version,
        effective_date=payload.effective_date,
        is_placeholder=payload.is_placeholder,
        notice=payload.notice,
        bands=[b.model_dump() for b in payload.bands],
        is_active=False,
        created_by_id=created_by_id,
    )
    db.add(row)

    if activate:
        _deactivate_all(db)
        row.is_active = True

    db.commit()
    db.refresh(row)
    return row


def activate_version(db: Session, version: str) -> RulesetVersion:
    row = db.query(RulesetVersion).filter(RulesetVersion.version == version).first()
    if row is None:
        raise VersionNotFoundError(f"Ruleset version '{version}' not found")

    _deactivate_all(db)
    row.is_active = True
    db.commit()
    db.refresh(row)
    return row


def _deactivate_all(db: Session) -> None:
    db.query(RulesetVersion).filter(RulesetVersion.is_active.is_(True)).update({"is_active": False})
