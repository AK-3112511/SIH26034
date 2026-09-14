"""Add LOW_CONFIDENCE_CALIBRATION to scan_status_enum

Revision ID: 0003_add_low_confidence_calibration
Revises: 0002_add_users_and_audit_logs
Create Date: 2026-09-03 10:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_add_low_confidence_calibration"
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
