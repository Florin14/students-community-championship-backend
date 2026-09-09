from fastapi import Depends, Path, status
from sqlalchemy.orm import Session

from constants import MatchEventStatus
from extensions.sqlalchemy import get_db
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.match.models import MatchResponse
from modules.match.services import load_match_full

from .router import router


@router.get("/{id}", response_model=MatchResponse)
async def get_match(id: int = Path(...), db: Session = Depends(get_db)):
    match = load_match_full(db, id)

    if match is None:
        raise ErrorException(
            Error.NOT_FOUND,
            message="Match not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Public view: the timeline shows what happened, not what was mistyped.
    # The console reads GET /matches/{id}/events?includeVoided=true instead.
    match.events = sorted(
        [
            event
            for event in match.events
            if event.status == MatchEventStatus.ACTIVE
        ],
        key=lambda event: (event.minute is None, event.minute or 0, event.id),
    )

    return match
