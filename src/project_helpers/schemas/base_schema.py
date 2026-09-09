from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={
            Enum: lambda v: str(v),
            datetime: lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S"),
            date: lambda d: d.strftime("%Y-%m-%d"),
        },
    )
