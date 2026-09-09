from datetime import datetime
from typing import List, Optional

from pydantic import AliasChoices, Field, field_validator

from constants import CardType, MatchState
from project_helpers.schemas import BaseSchema, PaginationParams


def _decode_logo(value):
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8")
    return value


class MatchAdd(BaseSchema):
    seasonId: int
    homeTeamId: int
    awayTeamId: int
    round: Optional[int] = Field(None, ge=1)
    timestamp: datetime
    fieldId: Optional[int] = None
    location: Optional[str] = Field(None, max_length=160)
    operatorIds: List[int] = Field(default_factory=list)


class MatchUpdate(BaseSchema):
    round: Optional[int] = Field(None, ge=1)
    homeTeamId: Optional[int] = None
    awayTeamId: Optional[int] = None
    timestamp: Optional[datetime] = None
    fieldId: Optional[int] = None
    location: Optional[str] = Field(None, max_length=160)
    state: Optional[MatchState] = None


class MatchOperatorsSet(BaseSchema):
    """Replace the full set of operators assigned to a match."""

    operatorIds: List[int] = Field(default_factory=list)


class MatchOperatorItem(BaseSchema):
    userId: int
    userName: Optional[str] = None
    userEmail: Optional[str] = None


class GoalInput(BaseSchema):
    teamId: int
    scorerId: Optional[int] = None
    assistPlayerId: Optional[int] = None
    minute: Optional[int] = Field(None, ge=0, le=150)


class CardInput(BaseSchema):
    teamId: int
    playerId: int
    cardType: CardType
    minute: Optional[int] = Field(None, ge=0, le=150)


class MatchResultSet(BaseSchema):
    scoreHome: int = Field(..., ge=0)
    scoreAway: int = Field(..., ge=0)
    goals: List[GoalInput] = Field(default_factory=list)
    cards: List[CardInput] = Field(default_factory=list)


class GoalItem(BaseSchema):
    id: int
    teamId: int
    scorerId: Optional[int] = None
    scorerName: Optional[str] = None
    assistPlayerId: Optional[int] = None
    assistName: Optional[str] = None
    minute: Optional[int] = None


class CardItem(BaseSchema):
    id: int
    teamId: int
    playerId: Optional[int] = None
    playerName: Optional[str] = None
    cardType: CardType
    minute: Optional[int] = None


class MatchItem(BaseSchema):
    id: int
    seasonId: int
    seasonName: Optional[str] = None
    round: Optional[int] = None
    homeTeamId: int
    awayTeamId: int
    homeTeamName: Optional[str] = None
    awayTeamName: Optional[str] = None
    homeTeamShortName: Optional[str] = None
    awayTeamShortName: Optional[str] = None
    homeTeamLogo: Optional[str] = None
    awayTeamLogo: Optional[str] = None
    homeTeamColor: Optional[str] = None
    awayTeamColor: Optional[str] = None
    timestamp: datetime
    fieldId: Optional[int] = None
    fieldName: Optional[str] = None
    location: Optional[str] = None
    scoreHome: Optional[int] = None
    scoreAway: Optional[int] = None
    state: MatchState
    startedAt: Optional[datetime] = None
    isClockRunning: bool = False
    currentMinute: Optional[int] = None
    isLocked: bool = False

    @field_validator("homeTeamLogo", "awayTeamLogo", mode="before")
    @classmethod
    def decode_logos(cls, value):
        return _decode_logo(value)


class MatchResponse(MatchItem):
    goals: List[GoalItem] = []
    cards: List[CardItem] = []
    confirmedAt: Optional[datetime] = None
    confirmedByName: Optional[str] = None
    operators: List[MatchOperatorItem] = Field(
        default_factory=list, validation_alias="matchOperators"
    )


class MatchListParams(PaginationParams):
    seasonId: Optional[int] = Field(
        None, validation_alias=AliasChoices("seasonId", "season_id")
    )
    fieldId: Optional[int] = Field(
        None, validation_alias=AliasChoices("fieldId", "field_id")
    )
    teamId: Optional[int] = Field(
        None, validation_alias=AliasChoices("teamId", "team_id")
    )
    round: Optional[int] = None
    state: Optional[MatchState] = None


class MatchListResponse(BaseSchema):
    data: List[MatchItem] = []
