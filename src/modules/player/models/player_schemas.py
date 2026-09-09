from datetime import datetime
from typing import List, Optional

from pydantic import AliasChoices, Field, field_validator

from constants import PlayerPositions
from project_helpers.functions import process_and_convert_image_to_base64
from project_helpers.schemas import BaseSchema, PaginationParams


class AvatarInputMixin(BaseSchema):
    avatar: Optional[bytes] = None

    @field_validator("avatar", mode="before")
    @classmethod
    def encode_avatar(cls, value):
        if isinstance(value, str) and value:
            return process_and_convert_image_to_base64(value)
        return value


class PlayerAdd(AvatarInputMixin):
    name: str = Field(..., min_length=1, max_length=80)
    position: Optional[PlayerPositions] = None
    shirtNumber: Optional[int] = Field(None, ge=0, le=99)
    teamId: Optional[int] = None


class PlayerUpdate(AvatarInputMixin):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    position: Optional[PlayerPositions] = None
    shirtNumber: Optional[int] = Field(None, ge=0, le=99)
    teamId: Optional[int] = None


class PlayerItem(BaseSchema):
    id: int
    name: str
    position: Optional[PlayerPositions] = None
    shirtNumber: Optional[int] = None
    avatar: Optional[str] = None
    teamId: Optional[int] = None
    teamName: Optional[str] = None
    teamShortName: Optional[str] = None
    goals: int = 0
    assists: int = 0
    yellowCards: int = 0
    redCards: int = 0

    @field_validator("avatar", mode="before")
    @classmethod
    def decode_avatar(cls, value):
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8")
        return value


class PlayerResponse(PlayerItem):
    pass


class PlayerListParams(PaginationParams):
    teamId: Optional[int] = Field(
        None, validation_alias=AliasChoices("teamId", "team_id")
    )
    position: Optional[PlayerPositions] = None
    search: Optional[str] = None


class PlayerListResponse(BaseSchema):
    data: List[PlayerItem] = []


class PlayerEventItem(BaseSchema):
    matchId: int
    timestamp: datetime
    homeTeamName: Optional[str] = None
    awayTeamName: Optional[str] = None
    scoreHome: Optional[int] = None
    scoreAway: Optional[int] = None
    type: str
    minute: Optional[int] = None


class PlayerEventsResponse(BaseSchema):
    data: List[PlayerEventItem] = []
