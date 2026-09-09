from sqlalchemy import Column, LargeBinary, String, Text
from sqlalchemy.orm import relationship

from extensions.sqlalchemy import BigIntPK, SqlBaseModel


class TeamModel(SqlBaseModel):
    __tablename__ = "teams"

    id = Column(BigIntPK, primary_key=True, index=True)
    name = Column(String(80), nullable=False, unique=True)
    shortName = Column("short_name", String(8), nullable=True)
    faculty = Column(String(120), nullable=True)
    description = Column(Text, nullable=True)
    color = Column(String(9), nullable=True)
    logo = Column(LargeBinary, nullable=True)

    players = relationship("PlayerModel", back_populates="team")
    seasonTeams = relationship(
        "SeasonTeamModel",
        back_populates="team",
        cascade="all, delete-orphan",
    )

    @property
    def playerCount(self):
        return len(self.players)
