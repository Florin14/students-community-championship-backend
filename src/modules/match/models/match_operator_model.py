from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship

from extensions.sqlalchemy import BigIntPK, SqlBaseModel


class MatchOperatorModel(SqlBaseModel):
    """Which operators may score which match.

    Section 6 of the plan: "Fiecare operator trebuie sa vada si sa modifice
    numai meciul sau terenul la care este repartizat." This table is what
    `MatchAccess` checks before allowing a write.
    """

    __tablename__ = "match_operators"
    __table_args__ = (
        UniqueConstraint("match_id", "user_id", name="uq_match_operator"),
    )

    id = Column(BigIntPK, primary_key=True, index=True)
    matchId = Column(
        "match_id",
        BigIntPK,
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    userId = Column(
        "user_id",
        BigIntPK,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assignedAt = Column(
        "assigned_at", DateTime, nullable=False, server_default=func.now()
    )

    match = relationship("MatchModel", back_populates="matchOperators")
    user = relationship("UserModel")

    @property
    def userName(self):
        return self.user.name if self.user else None

    @property
    def userEmail(self):
        return self.user.email if self.user else None
