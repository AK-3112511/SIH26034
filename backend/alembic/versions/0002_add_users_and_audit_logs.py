"""Add users and audit_log tables with user_role_enum and GIN index

Revision ID: 0002_add_users_and_audit_logs
Revises: 0001_initial_schema_postgis
Create Date: 2026-09-01 07:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002_add_users_and_audit_logs'
down_revision: Union[str, None] = '0001_initial_schema_postgis'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create user_role_enum type
    user_role_enum = postgresql.ENUM('field_lmo', 'senior_lmo', 'admin', name='user_role_enum')
    user_role_enum.create(op.get_bind(), checkfirst=True)

    # 2. Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.Text(), nullable=False),
        sa.Column('full_name', sa.Text(), nullable=False),
        sa.Column('role', postgresql.ENUM('field_lmo', 'senior_lmo', 'admin', name='user_role_enum', create_type=False), nullable=False),
        sa.Column('district', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        sa.UniqueConstraint('username', name=op.f('uq_users_username')),
        sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_index('idx_users_username', 'users', ['username'], unique=True)
    op.create_index('idx_users_email', 'users', ['email'], unique=True)
    op.create_index('idx_users_role', 'users', ['role'], unique=False)

    # 3. Create append-only audit_log table
    op.create_table(
        'audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('target_type', sa.Text(), nullable=False),
        sa.Column('target_id', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_log_actor_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_log'))
    )
    op.create_index('idx_audit_log_actor_id', 'audit_log', ['actor_id'], unique=False)
    op.create_index('idx_audit_log_action', 'audit_log', ['action'], unique=False)
    op.create_index('idx_audit_log_target_type', 'audit_log', ['target_type'], unique=False)
    op.create_index('idx_audit_log_target_id', 'audit_log', ['target_id'], unique=False)
    op.create_index('idx_audit_log_timestamp', 'audit_log', ['timestamp'], unique=False)
    op.create_index('idx_audit_log_detail', 'audit_log', ['detail'], unique=False, postgresql_using='gin')


def downgrade() -> None:
    # 1. Drop audit_log table and indexes
    op.drop_index('idx_audit_log_detail', table_name='audit_log', postgresql_using='gin')
    op.drop_index('idx_audit_log_timestamp', table_name='audit_log')
    op.drop_index('idx_audit_log_target_id', table_name='audit_log')
    op.drop_index('idx_audit_log_target_type', table_name='audit_log')
    op.drop_index('idx_audit_log_action', table_name='audit_log')
    op.drop_index('idx_audit_log_actor_id', table_name='audit_log')
    op.drop_table('audit_log')

    # 2. Drop users table and indexes
    op.drop_index('idx_users_role', table_name='users')
    op.drop_index('idx_users_email', table_name='users')
    op.drop_index('idx_users_username', table_name='users')
    op.drop_table('users')

    # 3. Drop user_role_enum
    op.execute('DROP TYPE IF EXISTS user_role_enum;')
