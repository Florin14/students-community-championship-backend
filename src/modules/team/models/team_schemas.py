from typing import List, Optional

from pydantic import AliasChoices, Field, field_validator

from project_helpers.functions import process_and_convert_image_to_base64
from project_helpers.schemas import BaseSchema, PaginationParams


class LogoInputMixin(BaseSchema):
    logo: Optional[bytes] = None

    @field_validator("logo", mode="before")
    @classmethod
    def encode_logo(cls, value):
        if isinstance(value, str) and value:
            return process_and_convert_image_to_base64(value)
        return value


class TeamAdd(LogoInputMixin):
    name: str = Field(..., min_length=1, max_length=80)
    shortName: Optional[str] = Field(None, max_length=8)
    faculty: Optional[str] = Field(None, max_length=120)
    description: Optional[str] = None
    color: Optional[str] = Field(None, max_length=9)


class TeamUpdate(LogoInputMixin):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    shortName: Optional[str] = Field(None, max_length=8)
    faculty: Optional[str] = Field(None, max_length=120)
    description: Optional[str] = None
    color: Optional[str] = Field(None, max_length=9)


class TeamItem(BaseSchema):
    id: int
    name: str
    shortName: Optional[str] = None
    faculty: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    logo: Optional[str] = None
    playerCount: int = 0

    @field_validator("logo", mode="before")
    @classmethod
    def decode_logo(cls, value):
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8")
        return value


class TeamResponse(TeamItem):
    pass


class TeamListParams(PaginationParams):
    seasonId: Optional[int] = Field(
        None, validation_alias=AliasChoices("seasonId", "season_id")
    )
    search: Optional[str] = None


class TeamListResponse(BaseSchema):
    data: List[TeamItem] = []
