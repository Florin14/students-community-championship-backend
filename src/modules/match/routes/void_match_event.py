from fastapi import Depends, Path, status
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from project_helpers.dependencies import MatchAccess, MatchContext
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.match.models import (
    MatchEventModel,
    MatchEventVoid,
    MatchEventWriteResponse,
)
from modules.match.services import void_match_event as void_event
from modules.standings.services import recalculate_match_standings

from .router import router


@router.post(
    "/{id}/events/{eventId}/void",
    response_model=MatchEventWriteResponse,
)
async def void_match_event(
    data: MatchEventVoid,
    eventId: int = Path(...),
    ctx: MatchContext = Depends(MatchAccess()),
    db: Session = Depends(get_db),
):
    """Cancel an event without deleting it.

    The row stays, with who voided it and when, so the match keeps a complete
    record of what was entered (plan, section 5).
    """
    event = (
        db.query(MatchEventModel)
        .filter(MatchEventModel.id == eventId)
        .first()
    )
    if event is None:
        raise ErrorException(
            Error.NOT_FOUND,
            message="Event not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    void_event(db, ctx.match, event, ctx.user, reason=data.reason)
    recalculate_match_standings(db, ctx.match)
    db.commit()
    db.refresh(event)

    return MatchEventWriteResponse(
        event=event,
        created=False,
        scoreHome=ctx.match.scoreHome,
        scoreAway=ctx.match.scoreAway,
        currentMinute=ctx.match.currentMinute,
    )
