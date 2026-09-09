from typing import List, Optional

from pydantic import field_validator

from project_helpers.schemas import BaseSchema


class StandingItem(BaseSchema):
    id: int
    seasonId: int
    teamId: int
    teamName: Optional[str] = None
    teamShortName: Optional[str] = None
    teamLogo: Optional[str] = None
    teamColor: Optional[str] = None
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goalsFor: int = 0
    goalsAgainst: int = 0
    goalDiff: int = 0
    points: int = 0
    form: str = ""

    @field_validator("teamLogo", mode="before")
    @classmethod
    def decode_logo(cls, value):
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8")
        return value


class StandingListResponse(BaseSchema):
    data: List[StandingItem] = []
