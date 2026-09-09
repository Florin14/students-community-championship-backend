from fastapi import Depends, status
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from project_helpers.dependencies import MatchAccess, MatchContext
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.match.models import MatchEventVoid, MatchEventWriteResponse
from modules.match.services import last_active_event
from modules.match.services import void_match_event as void_event
from modules.standings.services import recalculate_match_standings

from .router import router


@router.post("/{id}/events/undo", response_model=MatchEventWriteResponse)
async def undo_last_match_event(
    data: MatchEventVoid,
    ctx: MatchContext = Depends(MatchAccess()),
    db: Session = Depends(get_db),
):
    """Void the most recent active event on this match.

    The one-tap undo the console keeps permanently visible, so an operator does
    not have to find the right row in a list while the match carries on.
    """
    event = last_active_event(db, ctx.match.id)
    if event is None:
        raise ErrorException(
            Error.NOT_FOUND,
            message="There is nothing to undo on this match",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    void_event(db, ctx.match, event, ctx.user, reason=data.reason or "Undo")
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
