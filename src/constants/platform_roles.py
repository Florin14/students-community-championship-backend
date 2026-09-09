from enum import Enum


class PlatformRoles(str, Enum):
    """Platform roles, ordered by privilege.

    Section 6 of the implementation plan: an operator scores only the matches
    assigned to them, an administrator runs the competition, and a super-admin
    can additionally reopen and correct a confirmed match.
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
