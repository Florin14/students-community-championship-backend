from sqlalchemy import Column, Enum, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import relationship

from constants import PlayerPositions
from extensions.sqlalchemy import BigIntPK, SqlBaseModel


class PlayerModel(SqlBaseModel):
    __tablename__ = "players"

    id = Column(BigIntPK, primary_key=True, index=True)
    name = Column(String(80), nullable=False)
    position = Column(Enum(PlayerPositions), nullable=True)
    shirtNumber = Column("shirt_number", Integer, nullable=True)
    avatar = Column(LargeBinary, nullable=True)
    teamId = Column(
        "team_id",
        BigIntPK,
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    team = relationship("TeamModel", back_populates="players")

    @property
    def teamName(self):
        return self.team.name if self.team else None

    @property
    def teamShortName(self):
        return self.team.shortName if self.team else None
