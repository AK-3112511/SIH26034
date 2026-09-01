"""Initial schema setup with PostgreSQL 15, PostGIS, core tables, enums, GIN indexes, and location trigger

Revision ID: 0001_initial_schema_postgis
Revises: 
Create Date: 2026-09-01 07:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema_postgis'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable required PostgreSQL extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    op.execute('CREATE EXTENSION IF NOT EXISTS "postgis";')

    # 2. Create PostgreSQL ENUM types
    scan_source_enum = postgresql.ENUM('mobile', 'ecommerce', name='scan_source_enum')
    scan_source_enum.create(op.get_bind(), checkfirst=True)

    scan_status_enum = postgresql.ENUM('QUEUED', 'PASSED', 'FAILED', 'PENDING_REVIEW', 'CALIBRATION_FAILED', name='scan_status_enum')
    scan_status_enum.create(op.get_bind(), checkfirst=True)

    rule_status_enum = postgresql.ENUM('PASS', 'FAIL', 'UNVERIFIED', name='rule_status_enum')
    rule_status_enum.create(op.get_bind(), checkfirst=True)

    # 3. Create scans table
    op.create_table(
        'scans',
        sa.Column('scan_id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('source', postgresql.ENUM('mobile', 'ecommerce', name='scan_source_enum', create_type=False), nullable=False),
        sa.Column('image_url', sa.Text(), nullable=False),
        sa.Column('evidence_hash', sa.Text(), nullable=False),
        sa.Column('lat', sa.Float(precision=53), nullable=True),
        sa.Column('lng', sa.Float(precision=53), nullable=True),
        sa.Column('location', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True),
        sa.Column('captured_at_utc', sa.DateTime(timezone=True), nullable=True),
        sa.Column('mm_per_px', sa.Float(), nullable=True),
        sa.Column('pdp_area_cm2', sa.Float(), nullable=True),
        sa.Column('status', postgresql.ENUM('PASSED', 'FAILED', 'PENDING_REVIEW', 'CALIBRATION_FAILED', name='scan_status_enum', create_type=False), nullable=False),
        sa.Column('ruleset_version', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('scan_id', name=op.f('pk_scans'))
    )

    # GIST index for location column
    op.create_index('idx_scans_location', 'scans', ['location'], unique=False, postgresql_using='gist')

    # 4. Trigger function and trigger to derive location from lat/lng on INSERT and UPDATE
    op.execute("""
    CREATE OR REPLACE FUNCTION fn_derive_scan_location()
    RETURNS TRIGGER AS $$
    BEGIN
        IF NEW.lat IS NOT NULL AND NEW.lng IS NOT NULL THEN
            NEW.location := ST_SetSRID(ST_MakePoint(NEW.lng, NEW.lat), 4326);
        ELSE
            NEW.location := NULL;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE TRIGGER trg_derive_scan_location
    BEFORE INSERT OR UPDATE OF lat, lng ON scans
    FOR EACH ROW
    EXECUTE FUNCTION fn_derive_scan_location();
    """)

    # 5. Create extracted_fields table
    op.create_table(
        'extracted_fields',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('scan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('field_name', sa.Text(), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('bbox', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ocr_confidence', sa.Float(), nullable=True),
        sa.Column('semantic_confidence', sa.Float(), nullable=True),
        sa.Column('font_height_mm', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['scan_id'], ['scans.scan_id'], name=op.f('fk_extracted_fields_scan_id_scans'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_extracted_fields'))
    )
    op.create_index('idx_extracted_fields_scan_id', 'extracted_fields', ['scan_id'], unique=False)
    op.create_index('idx_extracted_fields_bbox', 'extracted_fields', ['bbox'], unique=False, postgresql_using='gin')

    # 6. Create rule_results table
    op.create_table(
        'rule_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('scan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_id', sa.Text(), nullable=False),
        sa.Column('status', postgresql.ENUM('PASS', 'FAIL', 'UNVERIFIED', name='rule_status_enum', create_type=False), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['scan_id'], ['scans.scan_id'], name=op.f('fk_rule_results_scan_id_scans'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_rule_results')),
        sa.UniqueConstraint('scan_id', 'rule_id', name='uq_rule_results_scan_rule')
    )
    op.create_index('idx_rule_results_scan_id', 'rule_results', ['scan_id'], unique=False)
    op.create_index('idx_rule_results_evidence', 'rule_results', ['evidence'], unique=False, postgresql_using='gin')

    # 7. Create challans table
    op.create_table(
        'challans',
        sa.Column('challan_id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('scan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('lmo_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('pdf_url', sa.Text(), nullable=True),
        sa.Column('pdf_hash', sa.Text(), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['scan_id'], ['scans.scan_id'], name=op.f('fk_challans_scan_id_scans'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('challan_id', name=op.f('pk_challans'))
    )
    op.create_index('idx_challans_scan_id', 'challans', ['scan_id'], unique=False)


def downgrade() -> None:
    # 1. Drop tables in reverse order
    op.drop_index('idx_challans_scan_id', table_name='challans')
    op.drop_table('challans')

    op.drop_index('idx_rule_results_evidence', table_name='rule_results', postgresql_using='gin')
    op.drop_index('idx_rule_results_scan_id', table_name='rule_results')
    op.drop_table('rule_results')

    op.drop_index('idx_extracted_fields_bbox', table_name='extracted_fields', postgresql_using='gin')
    op.drop_index('idx_extracted_fields_scan_id', table_name='extracted_fields')
    op.drop_table('extracted_fields')

    # 2. Drop trigger and function
    op.execute('DROP TRIGGER IF EXISTS trg_derive_scan_location ON scans;')
    op.execute('DROP FUNCTION IF EXISTS fn_derive_scan_location();')

    # 3. Drop scans table
    op.drop_index('idx_scans_location', table_name='scans', postgresql_using='gist')
    op.drop_table('scans')

    # 4. Drop ENUM types
    op.execute('DROP TYPE IF EXISTS rule_status_enum;')
    op.execute('DROP TYPE IF EXISTS scan_status_enum;')
    op.execute('DROP TYPE IF EXISTS scan_source_enum;')
