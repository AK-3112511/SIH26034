"""Add LOW_CONFIDENCE_CALIBRATION to scan_status_enum

Revision ID: 0003_low_conf_calib
Revises: 0002_add_users_and_audit_logs
Create Date: 2026-09-03 10:00:00.000000

Note: revision id shortened from the original
'0003_add_low_confidence_calibration' (36 chars) to fit Alembic's default
alembic_version.version_num VARCHAR(32) column — the long id made
`alembic upgrade` fail on any real database with a StringDataRightTruncation
error (discovered during Phase 6.1 verification against a live PostGIS
instance; see /audit/progress.md Log Entry #021). Safe to rename here since
no environment has ever successfully completed a migration against a
persistent database with the old id (confirmed during that same
verification) — there is no live alembic_version row anywhere referencing it.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_low_conf_calib"
down_revision: str | None = "0002_add_users_and_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE scan_status_enum ADD VALUE IF NOT EXISTS 'LOW_CONFIDENCE_CALIBRATION'")


def downgrade() -> None:
    # PostgreSQL does not natively support removing values from an ENUM type without recreating it
    pass
