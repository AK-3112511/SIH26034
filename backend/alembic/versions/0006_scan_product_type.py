"""scans.product_type container hint

Revision ID: 0006_product_type
Revises: 0005_events_identity
Create Date: 2026-09-22
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_product_type"
down_revision: str | None = "0005_events_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("product_type", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("scans", "product_type")
