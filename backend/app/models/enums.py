import enum


def enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """``values_callable`` for SQLAlchemy ``ENUM`` columns.

    Without this SQLAlchemy binds the member *name* (``MOBILE``) instead of the
    *value* (``mobile``) that the PostgreSQL enum type was created with.
    """
    return [member.value for member in enum_cls]


class ScanSource(str, enum.Enum):
    MOBILE = "mobile"
    ECOMMERCE = "ecommerce"

class ScanStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    PENDING_REVIEW = "PENDING_REVIEW"
    CALIBRATION_FAILED = "CALIBRATION_FAILED"
    LOW_CONFIDENCE_CALIBRATION = "LOW_CONFIDENCE_CALIBRATION"
    PROCESSING = "PROCESSING"
    PROCESSING_FAILED = "PROCESSING_FAILED"

class RuleStatus(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNVERIFIED = "UNVERIFIED"

class UserRole(str, enum.Enum):
    FIELD_LMO = "field_lmo"
    SENIOR_LMO = "senior_lmo"
    ADMIN = "admin"
