from datetime import datetime

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
    fieldId = Column(
        "field_id",
        BigIntPK,
        ForeignKey("fields.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    location = Column(String(160), nullable=True)
    scoreHome = Column("score_home", Integer, nullable=True)
    scoreAway = Column("score_away", Integer, nullable=True)
    state = Column(
        Enum(MatchState), nullable=False, default=MatchState.SCHEDULED
    )

    # --- Clock ------------------------------------------------------------
    # `elapsedSeconds` accumulates completed playing time; `runningSince` is
    # set while the clock ticks and cleared on pause, so the current minute
    # survives a server restart without a background timer.
    startedAt = Column("started_at", DateTime, nullable=True)
    runningSince = Column("running_since", DateTime, nullable=True)
    elapsedSeconds = Column(
        "elapsed_seconds", Integer, nullable=False, default=0
    )

    # --- Result confirmation ----------------------------------------------
    # Once `lockedAt` is set the match refuses writes; only a super-admin can
    # clear it by reopening the match (plan, section 6).
    lockedAt = Column("locked_at", DateTime, nullable=True)
    confirmedAt = Column("confirmed_at", DateTime, nullable=True)
    confirmedById = Column(
        "confirmed_by_id",
        BigIntPK,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    season = relationship("SeasonModel", back_populates="matches")
    field = relationship("FieldModel", back_populates="matches")
    confirmedBy = relationship("UserModel", foreign_keys=[confirmedById])
    homeTeam = relationship("TeamModel", foreign_keys=[homeTeamId])
    awayTeam = relationship("TeamModel", foreign_keys=[awayTeamId])
    goals = relationship(
        "GoalModel", back_populates="match", cascade="all, delete-orphan"
    )
    cards = relationship(
        "CardModel", back_populates="match", cascade="all, delete-orphan"
    )
    matchOperators = relationship(
        "MatchOperatorModel",
        back_populates="match",
        cascade="all, delete-orphan",
    )

    @property
    def isLocked(self) -> bool:
        return self.lockedAt is not None

    @property
    def isClockRunning(self) -> bool:
        return self.runningSince is not None

    @property
    def playedSeconds(self) -> int:
        """Playing time so far, including the segment currently running."""
        seconds = self.elapsedSeconds or 0
        if self.runningSince is not None:
            delta = datetime.utcnow() - self.runningSince
            seconds += max(0, int(delta.total_seconds()))
        return seconds

    @property
    def currentMinute(self):
        """The minute to pre-fill on the operator console, 1-based.

        None before kickoff, so the console asks for a minute instead of
        silently recording everything in the first minute.
        """
        if self.startedAt is None:
            return None
        return self.playedSeconds // 60 + 1

    @property
    def confirmedByName(self):
        return self.confirmedBy.name if self.confirmedBy else None

    @property
    def fieldName(self):
        return self.field.name if self.field else None

    @property
    def operatorIds(self):
        return [link.userId for link in self.matchOperators]

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
