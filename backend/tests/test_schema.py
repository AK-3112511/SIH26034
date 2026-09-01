"""Unit test to verify SQLAlchemy model definitions against §11 schema requirements."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ENUM, JSONB
from geoalchemy2 import Geometry

from app.models import (
    Base,
    Scan,
    ExtractedField,
    RuleResult,
    Challan,
    ScanSource,
    ScanStatus,
    RuleStatus
)

def test_tables_registered():
    table_names = set(Base.metadata.tables.keys())
    expected = {"scans", "extracted_fields", "rule_results", "challans", "users", "audit_log"}
    assert table_names == expected, f"Expected tables {expected}, but found {table_names}"

def test_users_table_structure():
    table = Base.metadata.tables["users"]
    col_names = {c.name for c in table.columns}
    expected_cols = {
        "id", "username", "email", "hashed_password",
        "full_name", "role", "district", "is_active", "created_at"
    }
    assert expected_cols == col_names

def test_audit_log_table_structure():
    table = Base.metadata.tables["audit_log"]
    col_names = {c.name for c in table.columns}
    expected_cols = {"id", "actor_id", "action", "target_type", "target_id", "timestamp", "detail"}
    assert expected_cols == col_names

def test_scans_table_structure():
    table = Base.metadata.tables["scans"]
    
    # Columns check
    col_names = {c.name for c in table.columns}
    expected_cols = {
        "scan_id", "source", "image_url", "evidence_hash",
        "lat", "lng", "location", "captured_at_utc",
        "mm_per_px", "pdp_area_cm2", "status", "ruleset_version", "created_at"
    }
    assert expected_cols == col_names

    # Primary key check
    assert [c.name for c in table.primary_key.columns] == ["scan_id"]
    assert isinstance(table.columns["scan_id"].type, UUID)

    # PostGIS Location Column check
    loc_type = Scan.location.type
    assert isinstance(loc_type, Geometry)
    assert loc_type.geometry_type in ("POINT", "GEOMETRY")
    assert loc_type.name == "geometry"

def test_extracted_fields_table_structure():
    table = Base.metadata.tables["extracted_fields"]
    col_names = {c.name for c in table.columns}
    expected_cols = {
        "id", "scan_id", "field_name", "raw_text",
        "bbox", "ocr_confidence", "semantic_confidence", "font_height_mm"
    }
    assert expected_cols == col_names
    assert isinstance(table.columns["bbox"].type, JSONB)

    # FK check
    fk = list(table.foreign_keys)[0]
    assert fk.column.table.name == "scans"
    assert fk.column.name == "scan_id"

def test_rule_results_table_structure():
    table = Base.metadata.tables["rule_results"]
    col_names = {c.name for c in table.columns}
    expected_cols = {"id", "scan_id", "rule_id", "status", "reason", "evidence"}
    assert expected_cols == col_names
    assert isinstance(table.columns["evidence"].type, JSONB)

    # Unique constraint check on (scan_id, rule_id)
    unique_constraints = [
        c for c in table.constraints if isinstance(c, UniqueConstraint)
    ]
    u_cols = [{col.name for col in uc.columns} for uc in unique_constraints]
    assert {"scan_id", "rule_id"} in u_cols

def test_challans_table_structure():
    table = Base.metadata.tables["challans"]
    col_names = {c.name for c in table.columns}
    expected_cols = {"challan_id", "scan_id", "lmo_id", "pdf_url", "pdf_hash", "generated_at"}
    assert expected_cols == col_names
    
    # FK check
    fk = list(table.foreign_keys)[0]
    assert fk.column.table.name == "scans"
    assert fk.column.name == "scan_id"

if __name__ == "__main__":
    test_tables_registered()
    test_scans_table_structure()
    test_extracted_fields_table_structure()
    test_rule_results_table_structure()
    test_challans_table_structure()
    print("All schema verification tests passed successfully!")
