"""
Standardized error codes for API responses.

Phase 4: Error Handling & Validation
- Req 4.2: Error response formatting
- Property 35: Standardized error codes
"""


class ErrorCode:
    """Machine-readable error codes for frontend handling."""

    # General errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    ACCESS_DENIED = "ACCESS_DENIED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"

    # CSV/Bulk errors
    CSV_INVALID_STRUCTURE = "CSV_INVALID_STRUCTURE"
    CSV_TOO_MANY_ROWS = "CSV_TOO_MANY_ROWS"
    CSV_INVALID_FILE_TYPE = "CSV_INVALID_FILE_TYPE"
    CSV_EMPTY_FILE = "CSV_EMPTY_FILE"

    # Duplicate errors
    DUPLICATE_IN_CSV = "DUPLICATE_IN_CSV"
    DUPLICATE_IN_DATABASE = "DUPLICATE_IN_DATABASE"
    DUPLICATE_ASSIGNMENT = "DUPLICATE_ASSIGNMENT"

    # Field validation errors
    INVALID_DATE_FORMAT = "INVALID_DATE_FORMAT"
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
    INVALID_COORDINATES = "INVALID_COORDINATES"
    INVALID_PHONE_FORMAT = "INVALID_PHONE_FORMAT"
    INVALID_EMAIL_FORMAT = "INVALID_EMAIL_FORMAT"
    INVALID_VENDOR_ID_FORMAT = "INVALID_VENDOR_ID_FORMAT"
    INVALID_CAMPAIGN_TYPE = "INVALID_CAMPAIGN_TYPE"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"

    # Reference errors
    CAMPAIGN_NOT_FOUND = "CAMPAIGN_NOT_FOUND"
    VENDOR_NOT_FOUND = "VENDOR_NOT_FOUND"
    ASSIGNMENT_NOT_FOUND = "ASSIGNMENT_NOT_FOUND"

    # Service errors
    GEOCODING_FAILED = "GEOCODING_FAILED"
    SMS_FAILED = "SMS_FAILED"
    DB_CONSTRAINT_VIOLATION = "DB_CONSTRAINT_VIOLATION"


class ErrorDetail:
    """Structured error detail for API responses."""

    def __init__(self, code: str, message: str, field: str = None, row: int = None):
        self.code = code
        self.message = message
        self.field = field
        self.row = row

    def to_dict(self):
        result = {"code": self.code, "message": self.message}
        if self.field:
            result["field"] = self.field
        if self.row:
            result["row"] = self.row
        return result
