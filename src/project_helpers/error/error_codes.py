from enum import Enum


class Error(Enum):
    # Auth
    INVALID_CREDENTIALS = ("E0010", "Invalid email or password")
    TOKEN_NOT_FOUND = ("E0011", "Authorization token is missing")
    INVALID_TOKEN = ("E0012", "Authorization token is invalid or expired")
    FORBIDDEN = ("E0013", "You do not have permission to perform this action")
    USER_NOT_FOUND = ("E0014", "User not found")

    # Generic
    NOT_FOUND = ("E0030", "Resource not found")
    VALIDATION_ERROR = ("E0031", "Validation error")
    CONFLICT = ("E0032", "Resource already exists")
    BAD_REQUEST = ("E0033", "Bad request")

    # Files
    INVALID_IMAGE = ("E0040", "Invalid image file")

    # Database
    DB_INSERT_ERROR = ("E0101", "Database write failed")
    DB_ACCESS_ERROR = ("E0102", "Database access failed")

    UNKNOWN = ("E9999", "Something went wrong")

    @property
    def code(self):
        return self.value[0]

    @property
    def message(self):
        return self.value[1]
