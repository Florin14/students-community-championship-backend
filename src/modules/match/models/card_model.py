from sqlalchemy import Column, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from constants import CardType
from extensions.sqlalchemy import BigIntPK, SqlBaseModel


class CardModel(SqlBaseModel):
    __tablename__ = "cards"

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
    playerId = Column(
        "player_id",
        BigIntPK,
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    playerNameSnapshot = Column("player_name_snapshot", String(80), nullable=True)
    cardType = Column("card_type", Enum(CardType), nullable=False)
    minute = Column(Integer, nullable=True)

    match = relationship("MatchModel", back_populates="cards")
    player = relationship("PlayerModel", foreign_keys=[playerId])

    @property
    def playerName(self):
        if self.player is not None:
            return self.player.name
        return self.playerNameSnapshot
