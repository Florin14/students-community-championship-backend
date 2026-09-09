from enum import Enum


class PlatformRoles(str, Enum):
    ADMIN = "ADMIN"

    def __str__(self):
        return self.value
