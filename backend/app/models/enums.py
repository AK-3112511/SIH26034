import enum

class ScanSource(str, enum.Enum):
    MOBILE = "mobile"
    ECOMMERCE = "ecommerce"

class ScanStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    PENDING_REVIEW = "PENDING_REVIEW"
    CALIBRATION_FAILED = "CALIBRATION_FAILED"

class RuleStatus(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNVERIFIED = "UNVERIFIED"

class UserRole(str, enum.Enum):
    FIELD_LMO = "field_lmo"
    SENIOR_LMO = "senior_lmo"
    ADMIN = "admin"
