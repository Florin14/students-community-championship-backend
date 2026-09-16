from datetime import datetime
from typing import List, Optional

from pydantic import AliasChoices, Field, field_validator

from constants import MatchState
from project_helpers.schemas import BaseSchema, PaginationParams

from .match_event_schemas import MatchEventItem


def _decode_logo(value):
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8")
    return value


def _clean_stream_url(value):
    """Empty input clears the link; anything kept must be a web URL.

    The value ends up in an iframe / anchor on the public match page, so a
    `javascript:` or bare-host string is refused here rather than escaped later.
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not value.lower().startswith(("http://", "https://")):
        raise ValueError("streamUrl must start with http:// or https://")
    return value


class MatchAdd(BaseSchema):
    seasonId: int
    homeTeamId: int
    awayTeamId: int
    round: Optional[int] = Field(None, ge=1)
    timestamp: datetime
    fieldId: Optional[int] = None
    location: Optional[str] = Field(None, max_length=160)
    streamUrl: Optional[str] = Field(None, max_length=500)
    operatorIds: List[int] = Field(default_factory=list)

    @field_validator("streamUrl", mode="before")
    @classmethod
    def clean_stream_url(cls, value):
        return _clean_stream_url(value)


class MatchUpdate(BaseSchema):
    round: Optional[int] = Field(None, ge=1)
    homeTeamId: Optional[int] = None
    awayTeamId: Optional[int] = None
    timestamp: Optional[datetime] = None
    fieldId: Optional[int] = None
    location: Optional[str] = Field(None, max_length=160)
    # Explicit null (or "") clears the link; an absent key leaves it alone.
    streamUrl: Optional[str] = Field(None, max_length=500)
    state: Optional[MatchState] = None

    @field_validator("streamUrl", mode="before")
    @classmethod
    def clean_stream_url(cls, value):
        return _clean_stream_url(value)


class MatchOperatorsSet(BaseSchema):
    """Replace the full set of operators assigned to a match."""

    operatorIds: List[int] = Field(default_factory=list)


class MatchOperatorItem(BaseSchema):
    userId: int
    userName: Optional[str] = None
    userEmail: Optional[str] = None


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
    streamUrl: Optional[str] = None
    scoreHome: Optional[int] = None
    scoreAway: Optional[int] = None
    state: MatchState
    startedAt: Optional[datetime] = None
    isClockRunning: bool = False
    currentMinute: Optional[int] = None
    # Playing time at the moment this response was built. The client keeps
    # ticking from here while `isClockRunning`, so it shows seconds without a
    # request per second.
    playedSeconds: int = 0
    isLocked: bool = False

    @field_validator("homeTeamLogo", "awayTeamLogo", mode="before")
    @classmethod
    def decode_logos(cls, value):
        return _decode_logo(value)


class MatchResponse(MatchItem):
    events: List[MatchEventItem] = []
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


class LiveMatchItem(MatchItem):
    """A match in progress, with its timeline, for the public live views."""

    events: List[MatchEventItem] = []


class LiveMatchesResponse(BaseSchema):
    """The live payload plus a fingerprint of it.

    `revision` changes only when something a viewer would notice changes - a
    score, a state, a new or voided event. The clock is deliberately excluded:
    the client ticks the minute itself from `startedAt` and `elapsedSeconds`, so
    polling does not report a change every sixty seconds.
    """

    data: List[LiveMatchItem] = []
    revision: str = ""
    serverTime: datetime
