from enum import Enum


class AttendanceStatus(str, Enum):
    PRESENT = "PRESENT"
    VOIDED = "VOIDED"

    def __str__(self):
        return self.value
