from enum import Enum


class PlatformRoles(str, Enum):
    """Platform roles, ordered by privilege.

    Operators verify identity and attendance and score any open match.
    An administrator runs the competition; a super-admin can reopen a result.
    Competition management remains restricted to administrators.
    """

    OPERATOR = "OPERATOR"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"

    def __str__(self):
        return self.value

    @property
    def level(self) -> int:
        return _ROLE_LEVELS[self.value]

    def covers(self, required: "PlatformRoles") -> bool:
        """True when this role satisfies a requirement for `required`.

        Roles are hierarchical: asking for ADMIN also admits SUPER_ADMIN.
        """
        return self.level >= required.level


_ROLE_LEVELS = {
    PlatformRoles.OPERATOR.value: 1,
    PlatformRoles.ADMIN.value: 2,
    PlatformRoles.SUPER_ADMIN.value: 3,
}
