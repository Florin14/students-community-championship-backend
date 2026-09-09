from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from extensions.sqlalchemy import BigIntPK, SqlBaseModel


class StandingModel(SqlBaseModel):
    __tablename__ = "standings"
    __table_args__ = (
        UniqueConstraint("season_id", "team_id", name="uq_standing_season_team"),
    )

    id = Column(BigIntPK, primary_key=True, index=True)
    seasonId = Column(
        "season_id",
        BigIntPK,
        ForeignKey("seasons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    teamId = Column(
        "team_id",
        BigIntPK,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    played = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    draws = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)
    goalsFor = Column("goals_for", Integer, nullable=False, default=0)
    goalsAgainst = Column("goals_against", Integer, nullable=False, default=0)
    points = Column(Integer, nullable=False, default=0)

    season = relationship("SeasonModel", back_populates="standings")
    team = relationship("TeamModel")

    @property
    def goalDiff(self):
        return (self.goalsFor or 0) - (self.goalsAgainst or 0)

    @property
    def teamName(self):
        return self.team.name if self.team else None

    @property
    def teamShortName(self):
        return self.team.shortName if self.team else None

    @property
    def teamLogo(self):
        return self.team.logo if self.team else None

    @property
    def teamColor(self):
        return self.team.color if self.team else None
