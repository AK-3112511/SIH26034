"""event_logs table, capture identity, product metadata, processing states

Revision ID: 0005_events_identity
Revises: e314bddd466a
Create Date: 2026-09-22

* ``event_logs`` — the Phase 7 real-time transport table was added to the ORM
  without a migration, so every deployment on a migrated database was missing it.
* ``scans.captured_by_id`` — the officer who uploaded the evidence.  Ingestion is
  authenticated from now on, so chain of custody starts at the capture.
* ``scans.product_name`` / ``scans.platform`` / ``scans.reference_object_type`` /
  ``scans.processing_error`` — product identity and diagnostics.
* ``challans.lmo_id`` gains an FK to ``users``.
* ``challans`` — one notice per scan (unique constraint).
* ``scan_status_enum`` gains ``PROCESSING`` and ``PROCESSING_FAILED`` so a scan
  can never sit in ``QUEUED`` forever after a pipeline crash.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_events_identity"
down_revision: str | None = "e314bddd466a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- enum values (ALTER TYPE ... ADD VALUE cannot run inside a transaction on PG < 12; PG 16 is fine)
    op.execute("ALTER TYPE scan_status_enum ADD VALUE IF NOT EXISTS 'PROCESSING'")
    op.execute("ALTER TYPE scan_status_enum ADD VALUE IF NOT EXISTS 'PROCESSING_FAILED'")

    # --- event_logs
    op.create_table(
        "event_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_district", sa.Text(), nullable=True),
        sa.Column("target_role", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_event_logs_event_type", "event_logs", ["event_type"])
    op.create_index("ix_event_logs_target_user_id", "event_logs", ["target_user_id"])
    op.create_index("ix_event_logs_target_district", "event_logs", ["target_district"])
    op.create_index("ix_event_logs_target_role", "event_logs", ["target_role"])
    op.create_index("ix_event_logs_created_at", "event_logs", ["created_at"])
    op.create_index("idx_event_logs_created_at", "event_logs", ["created_at"])
    op.create_index("idx_event_logs_target", "event_logs", ["target_user_id", "target_district", "target_role"])

    # --- scans
    op.add_column("scans", sa.Column("captured_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("scans", sa.Column("product_name", sa.Text(), nullable=True))
    op.add_column("scans", sa.Column("platform", sa.Text(), nullable=True))
    op.add_column("scans", sa.Column("reference_object_type", sa.Text(), nullable=True))
    op.add_column("scans", sa.Column("processing_error", sa.Text(), nullable=True))
    op.create_index("ix_scans_captured_by_id", "scans", ["captured_by_id"])
    op.create_foreign_key("fk_scans_captured_by_users", "scans", "users", ["captured_by_id"], ["id"], ondelete="SET NULL")

    # --- challans
    op.create_foreign_key("fk_challans_lmo_users", "challans", "users", ["lmo_id"], ["id"], ondelete="SET NULL")
    # Keep only the most recent challan per scan before enforcing uniqueness.
    op.execute(
        """
        DELETE FROM challans c
        USING challans newer
        WHERE c.scan_id = newer.scan_id AND c.generated_at < newer.generated_at
        """
    )
    op.create_unique_constraint("uq_challans_scan", "challans", ["scan_id"])


def downgrade() -> None:
    op.drop_constraint("uq_challans_scan", "challans", type_="unique")
    op.drop_constraint("fk_challans_lmo_users", "challans", type_="foreignkey")
    op.drop_constraint("fk_scans_captured_by_users", "scans", type_="foreignkey")
    op.drop_index("ix_scans_captured_by_id", table_name="scans")
    for col in ("processing_error", "reference_object_type", "platform", "product_name", "captured_by_id"):
        op.drop_column("scans", col)
    op.drop_table("event_logs")
    # PostgreSQL cannot drop enum values; PROCESSING / PROCESSING_FAILED remain.
