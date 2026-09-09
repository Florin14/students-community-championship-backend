from typing import List, Optional

from fastapi import status

from project_helpers.error import Error


class ErrorException(Exception):
    def __init__(
        self,
        error: Error,
        message: Optional[str] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        fields: Optional[List[str]] = None,
    ):
        self.error = error
        self.message = message or error.message
        self.status_code = status_code
        self.fields = fields or []
        super().__init__(self.message)

    def as_dict(self):
        return {
            "code": self.error.code,
            "message": self.message,
            "fields": self.fields,
        }
