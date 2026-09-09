from sqlalchemy import Boolean, Column, Enum, String
from sqlalchemy.ext.hybrid import hybrid_property

from constants import PlatformRoles
from extensions.sqlalchemy import BigIntPK, SqlBaseModel
from project_helpers.functions import hash_password


class UserModel(SqlBaseModel):
    __tablename__ = "users"

    id = Column(BigIntPK, primary_key=True, index=True)
    name = Column(String(80), nullable=False)
    email = Column(String(120), nullable=False, unique=True, index=True)
    _password = Column("password", String(300), nullable=False)
    role = Column(
        Enum(PlatformRoles), nullable=False, default=PlatformRoles.ADMIN
    )
    isActive = Column("is_active", Boolean, nullable=False, default=True)

    @hybrid_property
    def password(self):
        return self._password

    @password.setter
    def password(self, value: str):
        self._password = hash_password(value)

    @property
    def platformRole(self) -> PlatformRoles:
        return PlatformRoles(str(self.role))

    def covers(self, required: PlatformRoles) -> bool:
        """True when this user's role satisfies a requirement for `required`."""
        return self.platformRole.covers(required)

    def get_claims(self):
        return {"userId": self.id, "role": str(self.role), "userName": self.name}
