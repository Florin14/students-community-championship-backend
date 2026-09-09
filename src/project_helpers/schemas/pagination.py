from typing import Optional

from pydantic import AliasChoices, Field

from .base_schema import BaseSchema


class PaginationParams(BaseSchema):
    """Optional pagination: without `limit` the full list is returned."""

    skip: int = Field(0, ge=0, validation_alias=AliasChoices("skip", "offset"))
    limit: Optional[int] = Field(
        None, ge=1, validation_alias=AliasChoices("limit", "pageSize")
    )

    def apply(self, query):
        if self.skip:
            query = query.offset(self.skip)
        if self.limit is not None:
            query = query.limit(self.limit)
        return query
