from datetime import datetime
from typing import List, Optional

from pydantic import Field, field_validator

from project_helpers.schemas import BaseSchema, PaginationParams


class TopPlayerItem(BaseSchema):
    playerId: int
    name: str
    teamId: Optional[int] = None
    teamName: Optional[str] = None
    avatar: Optional[str] = None
    goals: int = 0
    ownGoals: int = 0
    assists: int = 0
    yellowCards: int = 0
    redCards: int = 0

    @field_validator("avatar", mode="before")
    @classmethod
    def decode_avatar(cls, value):
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8")
        return value


class TopPlayersResponse(BaseSchema):
    data: List[TopPlayerItem] = []


class GoalsPerRoundItem(BaseSchema):
    round: Optional[int] = None
    matches: int = 0
    goals: int = 0


class GoalsPerRoundResponse(BaseSchema):
    data: List[GoalsPerRoundItem] = []


class OverviewResponse(BaseSchema):
    audienceTotal: int = 0
    audienceMatches: int = 0
    audienceAverage: Optional[float] = None
    audienceMax: Optional[int] = None
    attendances: int = 0
    attendancePlayers: int = 0
    attendanceMatches: int = 0
    teams: int = 0
    players: int = 0
    matchesPlayed: int = 0
    matchesUpcoming: int = 0
    goals: int = 0
    avgGoalsPerMatch: float = 0.0
    yellowCards: int = 0
    redCards: int = 0
    topScorerName: Optional[str] = None
    topScorerTeamName: Optional[str] = None
    topScorerGoals: int = 0


class AudienceStatsParams(PaginationParams):
    seasonId: Optional[int] = Field(None, gt=0)


class AudienceMatchItem(BaseSchema):
    matchId: int
    timestamp: datetime
    round: Optional[int] = None
    homeTeamName: str
    awayTeamName: str
    audience: int


class AudienceStatsResponse(BaseSchema):
    totalSpectators: int
    matchesWithAudience: int
    averageSpectators: Optional[float] = None
    maxSpectators: Optional[int] = None
    data: List[AudienceMatchItem] = Field(default_factory=list)
