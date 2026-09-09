from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from extensions.sqlalchemy import BigIntPK, SqlBaseModel


class GoalModel(SqlBaseModel):
    __tablename__ = "goals"

    id = Column(BigIntPK, primary_key=True, index=True)
    matchId = Column(
        "match_id",
        BigIntPK,
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    teamId = Column(
        "team_id", BigIntPK, ForeignKey("teams.id"), nullable=False
    )
    scorerId = Column(
        "scorer_id",
        BigIntPK,
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scorerNameSnapshot = Column("scorer_name_snapshot", String(80), nullable=True)
    assistPlayerId = Column(
        "assist_player_id",
        BigIntPK,
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assistNameSnapshot = Column("assist_name_snapshot", String(80), nullable=True)
    minute = Column(Integer, nullable=True)

    match = relationship("MatchModel", back_populates="goals")
    scorer = relationship("PlayerModel", foreign_keys=[scorerId])
    assistPlayer = relationship("PlayerModel", foreign_keys=[assistPlayerId])

    @property
    def scorerName(self):
        if self.scorer is not None:
            return self.scorer.name
        return self.scorerNameSnapshot

    @property
    def assistName(self):
        if self.assistPlayer is not None:
            return self.assistPlayer.name
        return self.assistNameSnapshot
