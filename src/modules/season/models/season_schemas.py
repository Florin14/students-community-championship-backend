from datetime import date
from typing import List, Optional

from pydantic import Field

from project_helpers.schemas import BaseSchema, PaginationParams


class SeasonAdd(BaseSchema):
    name: str = Field(..., min_length=1, max_length=80)
    description: Optional[str] = None
    startDate: Optional[date] = None
    endDate: Optional[date] = None
    isActive: bool = False


class SeasonUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    description: Optional[str] = None
    startDate: Optional[date] = None
    endDate: Optional[date] = None
    isActive: Optional[bool] = None


class SeasonItem(BaseSchema):
    id: int
    name: str
    description: Optional[str] = None
    startDate: Optional[date] = None
    endDate: Optional[date] = None
    isActive: bool
    teamCount: int = 0
    matchCount: int = 0


class SeasonResponse(SeasonItem):
    pass


class SeasonListParams(PaginationParams):
    pass


class SeasonListResponse(BaseSchema):
    data: List[SeasonItem] = []


class SeasonTeamsUpdate(BaseSchema):
    teamIds: List[int] = Field(default_factory=list)
