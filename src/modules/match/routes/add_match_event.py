from fastapi import Depends, status
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from project_helpers.dependencies import MatchAccess, MatchContext
from modules.match.models import (
    MatchEventAdd,
    MatchEventWriteResponse,
)
from modules.match.services import add_match_event as record_event
from modules.standings.services import recalculate_match_standings

from .router import router


@router.post(
    "/{id}/events",
    response_model=MatchEventWriteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_match_event(
    data: MatchEventAdd,
    ctx: MatchContext = Depends(MatchAccess()),
    db: Session = Depends(get_db),
):
    """Record a goal, own goal or card.

    Idempotent on `clientEventId`: replaying a request that already landed
    returns the stored event with `created: false` instead of duplicating it,
    which is what makes the console safe to retry on a bad connection.
    """
    event, created = record_event(db, ctx.match, ctx.user, data)

    # A reopened match is still FINISHED, so a correction has to move the table.
    recalculate_match_standings(db, ctx.match)
    db.commit()
    db.refresh(event)

    return MatchEventWriteResponse(
        event=event,
        created=created,
        scoreHome=ctx.match.scoreHome,
        scoreAway=ctx.match.scoreAway,
        currentMinute=ctx.match.currentMinute,
    )
