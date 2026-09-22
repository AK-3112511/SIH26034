"""add ruleset_versions table

Revision ID: e314bddd466a
Revises: 9bde9fb235b5
Create Date: 2026-09-15 02:24:08.941753

Note: hand-pruned from the raw `alembic revision --autogenerate` output.
Autogenerate also picked up ~750 lines of unrelated drift: tables owned by
the postgis_tiger_geocoder/topology extensions (which it wanted to DROP —
never do that, they're not part of our schema) and index/constraint
renames on unrelated tables (an artifact of some earlier migration hand-
authoring index names that don't match SQLAlchemy's naming convention).
Neither belongs in a "Phase 6.3: add ruleset_versions table" migration, so
only the one real table-creation diff is kept here.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e314bddd466a'
down_revision: str | None = '9bde9fb235b5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'ruleset_versions',
        sa.Column('version', sa.Text(), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('is_placeholder', sa.Boolean(), nullable=False),
        sa.Column('notice', sa.Text(), nullable=False),
        sa.Column('bands', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('version'),
    )


def downgrade() -> None:
    op.drop_table('ruleset_versions')
