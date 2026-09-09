from enum import Enum


class Error(Enum):
    # Auth
    INVALID_CREDENTIALS = ("E0010", "Invalid email or password")
    TOKEN_NOT_FOUND = ("E0011", "Authorization token is missing")
    INVALID_TOKEN = ("E0012", "Authorization token is invalid or expired")
    FORBIDDEN = ("E0013", "You do not have permission to perform this action")
    USER_NOT_FOUND = ("E0014", "User not found")
    ACCOUNT_DISABLED = ("E0015", "This account has been disabled")
    NOT_ASSIGNED_TO_MATCH = (
        "E0016",
        "You are not assigned to this match",
    )
    CANNOT_DEMOTE_SELF = (
        "E0017",
        "You cannot change your own role or disable your own account",
    )

    # Generic
    NOT_FOUND = ("E0030", "Resource not found")
    VALIDATION_ERROR = ("E0031", "Validation error")
    CONFLICT = ("E0032", "Resource already exists")
    BAD_REQUEST = ("E0033", "Bad request")

    # Match scoring
    MATCH_LOCKED = (
        "E0050",
        "The match result is confirmed and locked; a super-admin must reopen it",
    )
    MATCH_NOT_STARTED = ("E0051", "The match has not been started yet")
    INVALID_MATCH_TRANSITION = (
        "E0052",
        "The match cannot move to that state from its current one",
    )
    EVENT_ALREADY_VOIDED = ("E0053", "This event has already been voided")
    PLAYER_NOT_IN_TEAM = (
        "E0054",
        "The player does not belong to the team credited with the event",
    )

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
