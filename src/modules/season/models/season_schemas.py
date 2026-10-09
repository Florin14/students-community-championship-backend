from datetime import date
from typing import List, Literal, Optional

from pydantic import Field, field_validator, model_validator

from project_helpers.schemas import BaseSchema, PaginationParams


class SeasonCalendarPeriod(BaseSchema):
    startDate: date
    endDate: date
    label: str = Field(..., min_length=1, max_length=160)
    phase: Literal["LEAGUE", "ACADEMIC_BREAK", "PLAY_OFF", "FINAL_STAGES", "SEMIFINALS", "FINAL"]
    round: Optional[int] = Field(None, ge=1, le=999, strict=True)
    isBreak: bool = False

    @field_validator("label")
    @classmethod
    def clean_label(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Calendar activity must have a label")
        return value

    @model_validator(mode="after")
    def validate_period(self):
        if self.endDate < self.startDate:
            raise ValueError("Calendar period ends before it starts")
        if self.isBreak and self.round is not None:
            raise ValueError("A break cannot have a round")
        return self


class SeasonCalendarInput(BaseSchema):
    calendar: List[SeasonCalendarPeriod] = Field(default_factory=list, max_length=128)

    @field_validator("calendar")
    @classmethod
    def validate_calendar(cls, value):
        ordered = sorted(value, key=lambda period: period.startDate)
        for previous, current in zip(ordered, ordered[1:]):
            if current.startDate <= previous.endDate:
                raise ValueError("Calendar periods must not overlap")
        return ordered


class SeasonAdd(SeasonCalendarInput):
    name: str = Field(..., min_length=1, max_length=80)
    description: Optional[str] = None
    startDate: Optional[date] = None
    endDate: Optional[date] = None
    isActive: bool = False


class SeasonUpdate(SeasonCalendarInput):
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
    calendar: List[SeasonCalendarPeriod] = Field(default_factory=list)


class SeasonResponse(SeasonItem):
    pass


class SeasonListParams(PaginationParams):
    pass


class SeasonListResponse(BaseSchema):
    data: List[SeasonItem] = []


class SeasonTeamsUpdate(BaseSchema):
    teamIds: List[int] = Field(default_factory=list)
