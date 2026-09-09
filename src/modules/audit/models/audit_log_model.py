from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from extensions.sqlalchemy import BigIntPK, SqlBaseModel


class AuditLogModel(SqlBaseModel):
    """Append-only record of who changed what.

    Section 12 of the plan makes "fiecare modificare poate fi urmarita" a launch
    condition. Rows are never updated or deleted, and the actor's name is
    snapshotted so the trail stays readable after an account is removed.
    """

    __tablename__ = "audit_log"

    id = Column(BigIntPK, primary_key=True, index=True)
    createdAt = Column(
        "created_at",
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    entityType = Column("entity_type", String(40), nullable=False, index=True)
    entityId = Column("entity_id", BigIntPK, nullable=True, index=True)
    action = Column(String(40), nullable=False, index=True)

    # Denormalised so the trail for one match is a single indexed lookup, which
    # is how it is always read.
    matchId = Column(
        "match_id",
        BigIntPK,
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    userId = Column(
        "user_id",
        BigIntPK,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    userNameSnapshot = Column("user_name_snapshot", String(80), nullable=True)

    summary = Column(String(300), nullable=True)
    details = Column(JSON, nullable=True)

    user = relationship("UserModel", foreign_keys=[userId])

    @property
    def userName(self):
        if self.user is not None:
            return self.user.name
        return self.userNameSnapshot
