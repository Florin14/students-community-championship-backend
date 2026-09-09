from datetime import datetime
from typing import Any, List, Optional

from pydantic import AliasChoices, Field

from project_helpers.schemas import BaseSchema, PaginationParams


class AuditLogItem(BaseSchema):
    id: int
    createdAt: datetime
    entityType: str
    entityId: Optional[int] = None
    action: str
    matchId: Optional[int] = None
    userId: Optional[int] = None
    userName: Optional[str] = None
    summary: Optional[str] = None
    details: Optional[Any] = None


class AuditLogListParams(PaginationParams):
    matchId: Optional[int] = Field(
        None, validation_alias=AliasChoices("matchId", "match_id")
    )
    entityType: Optional[str] = Field(
        None, validation_alias=AliasChoices("entityType", "entity_type")
    )
    userId: Optional[int] = Field(
        None, validation_alias=AliasChoices("userId", "user_id")
    )


class AuditLogListResponse(BaseSchema):
    data: List[AuditLogItem] = []
