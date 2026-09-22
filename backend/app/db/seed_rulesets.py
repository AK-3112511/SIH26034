"""Seed the Schedule II ruleset versions.

Run from /backend:  python -m app.db.seed_rulesets

Inserts the statutory PCR 2011 Schedule II table as the active version and
keeps the original engineering placeholder as inactive history.  Idempotent —
existing rows are never modified (the table is append-only by design).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.ruleset_version import RulesetVersion
from app.services.rules.ruleset_config import PLACEHOLDER_SCHEDULE_II_V1, STATUTORY_SCHEDULE_II_2011


def seed_rulesets(db: Session) -> list[str]:
    messages: list[str] = []
    for ruleset, active in ((PLACEHOLDER_SCHEDULE_II_V1, False), (STATUTORY_SCHEDULE_II_2011, True)):
        row = db.query(RulesetVersion).filter(RulesetVersion.version == ruleset.version).first()
        if row is not None:
            messages.append(f"exists  {ruleset.version} (active={row.is_active})")
            continue
        if active:
            db.query(RulesetVersion).filter(RulesetVersion.is_active.is_(True)).update({"is_active": False})
        db.add(
            RulesetVersion(
                version=ruleset.version,
                effective_date=date.fromisoformat(ruleset.effective_date),
                is_placeholder=ruleset.is_placeholder,
                notice=ruleset.notice,
                bands=[b.to_dict() for b in ruleset.bands],
                is_active=active,
            )
        )
        messages.append(f"created {ruleset.version} (active={active})")
    db.commit()
    return messages


if __name__ == "__main__":
    session = SessionLocal()
    try:
        for line in seed_rulesets(session):
            print(f"  - {line}")
    finally:
        session.close()
