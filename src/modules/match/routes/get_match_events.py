from fastapi import Depends, Path
from sqlalchemy.orm import Session, joinedload

from constants import MatchEventStatus
from extensions.sqlalchemy import get_db
from modules.match.models import (
    MatchEventListParams,
    MatchEventListResponse,
    MatchEventModel,
)

from .router import router


@router.get("/{id}/events", response_model=MatchEventListResponse)
async def get_match_events(
    id: int = Path(...),
    params: MatchEventListParams = Depends(),
    db: Session = Depends(get_db),
):
    """The match timeline, earliest first.

    Voided events are hidden by default: the public timeline shows what
    happened, not what was mistyped. `includeVoided=true` returns the full
    record for the admin views.
    """
    query = (
        db.query(MatchEventModel)
        .options(
            joinedload(MatchEventModel.player),
            joinedload(MatchEventModel.assistPlayer),
            joinedload(MatchEventModel.createdBy),
            joinedload(MatchEventModel.voidedBy),
        )
        .filter(MatchEventModel.matchId == id)
    )

    if not params.includeVoided:
        query = query.filter(
            MatchEventModel.status == MatchEventStatus.ACTIVE
        )

    events = query.order_by(
        MatchEventModel.minute.asc().nullslast(),
        MatchEventModel.createdAt.asc(),
        MatchEventModel.id.asc(),
    ).all()

    return MatchEventListResponse(data=events)
