from typing import List, Optional

from pydantic import Field

from project_helpers.schemas import BaseSchema


class FieldAdd(BaseSchema):
    name: str = Field(..., min_length=1, max_length=80)
    shortName: Optional[str] = Field(None, max_length=12)
    location: Optional[str] = Field(None, max_length=160)
    description: Optional[str] = None


class FieldUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    shortName: Optional[str] = Field(None, max_length=12)
    location: Optional[str] = Field(None, max_length=160)
    description: Optional[str] = None


class FieldItem(BaseSchema):
    id: int
    name: str
    shortName: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None


class FieldResponse(FieldItem):
    pass


class FieldListResponse(BaseSchema):
    data: List[FieldItem] = []
