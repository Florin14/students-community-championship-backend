from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from extensions.sqlalchemy import BigIntPK, SqlBaseModel


class SeasonModel(SqlBaseModel):
    __tablename__ = "seasons"

    id = Column(BigIntPK, primary_key=True, index=True)
    name = Column(String(80), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    startDate = Column("start_date", Date, nullable=True)
    endDate = Column("end_date", Date, nullable=True)
    isActive = Column("is_active", Boolean, nullable=False, default=False)

    seasonTeams = relationship(
        "SeasonTeamModel",
        back_populates="season",
        cascade="all, delete-orphan",
    )
    matches = relationship(
        "MatchModel",
        back_populates="season",
        cascade="all, delete-orphan",
    )
    standings = relationship(
        "StandingModel",
        back_populates="season",
        cascade="all, delete-orphan",
    )

    @property
    def teamCount(self):
        return len(self.seasonTeams)

    @property
    def matchCount(self):
        return len(self.matches)


class SeasonTeamModel(SqlBaseModel):
    __tablename__ = "season_teams"
    __table_args__ = (
        UniqueConstraint("season_id", "team_id", name="uq_season_team"),
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

    season = relationship("SeasonModel", back_populates="seasonTeams")
    team = relationship("TeamModel", back_populates="seasonTeams")
