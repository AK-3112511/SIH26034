"""Add scan review assignment fields

Revision ID: 0003_add_scan_review_fields
Revises: 0002_add_users_and_audit_logs
Create Date: 2026-09-11 18:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_add_scan_review_fields"
down_revision: Union[str, None] = "0002_add_users_and_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scans",
        sa.Column("assigned_lmo_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("scans", sa.Column("reviewer_note", sa.Text(), nullable=True))
    op.create_foreign_key(
        op.f("fk_scans_assigned_lmo_id_users"),
        "scans",
        "users",
        ["assigned_lmo_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_scans_assigned_lmo_id", "scans", ["assigned_lmo_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_scans_assigned_lmo_id", table_name="scans")
    op.drop_constraint(op.f("fk_scans_assigned_lmo_id_users"), "scans", type_="foreignkey")
    op.drop_column("scans", "reviewer_note")
    op.drop_column("scans", "assigned_lmo_id")
