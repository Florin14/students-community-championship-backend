from datetime import datetime

from pydantic import Field

from project_helpers.schemas import BaseSchema


class PlayerQrRequest(BaseSchema):
    seasonId: int = Field(..., gt=0)
    regenerate: bool = False


class PlayerQrResponse(BaseSchema):
    playerId: int
    playerName: str
    teamId: int
    teamName: str
    seasonId: int
    seasonName: str
    issuedAt: datetime
    token: str


class PlayerQrRevoke(BaseSchema):
    seasonId: int = Field(..., gt=0)
