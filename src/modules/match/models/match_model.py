from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from constants import MatchState
from extensions.sqlalchemy import BigIntPK, SqlBaseModel


class MatchModel(SqlBaseModel):
    __tablename__ = "matches"

    id = Column(BigIntPK, primary_key=True, index=True)
    seasonId = Column(
        "season_id",
        BigIntPK,
        ForeignKey("seasons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    round = Column(Integer, nullable=True)
    homeTeamId = Column(
        "home_team_id", BigIntPK, ForeignKey("teams.id"), nullable=False
    )
    awayTeamId = Column(
        "away_team_id", BigIntPK, ForeignKey("teams.id"), nullable=False
    )
    timestamp = Column(DateTime, nullable=False)
    location = Column(String(160), nullable=True)
    scoreHome = Column("score_home", Integer, nullable=True)
    scoreAway = Column("score_away", Integer, nullable=True)
    state = Column(
        Enum(MatchState), nullable=False, default=MatchState.SCHEDULED
    )

    season = relationship("SeasonModel", back_populates="matches")
    homeTeam = relationship("TeamModel", foreign_keys=[homeTeamId])
    awayTeam = relationship("TeamModel", foreign_keys=[awayTeamId])
    goals = relationship(
        "GoalModel", back_populates="match", cascade="all, delete-orphan"
    )
    cards = relationship(
        "CardModel", back_populates="match", cascade="all, delete-orphan"
    )

    @property
    def seasonName(self):
        return self.season.name if self.season else None

    @property
    def homeTeamName(self):
        return self.homeTeam.name if self.homeTeam else None

    @property
    def awayTeamName(self):
        return self.awayTeam.name if self.awayTeam else None

    @property
    def homeTeamShortName(self):
        return self.homeTeam.shortName if self.homeTeam else None

    @property
    def awayTeamShortName(self):
        return self.awayTeam.shortName if self.awayTeam else None

    @property
    def homeTeamLogo(self):
        return self.homeTeam.logo if self.homeTeam else None

    @property
    def awayTeamLogo(self):
        return self.awayTeam.logo if self.awayTeam else None

    @property
    def homeTeamColor(self):
        return self.homeTeam.color if self.homeTeam else None

    @property
    def awayTeamColor(self):
        return self.awayTeam.color if self.awayTeam else None
