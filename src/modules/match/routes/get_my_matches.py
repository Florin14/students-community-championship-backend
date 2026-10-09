from fastapi import Depends
from sqlalchemy.orm import Session, joinedload

from constants import MatchState, PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import JwtRequired
from modules.match.models import (
    MatchListResponse,
    MatchModel,
)
from modules.match.services import attach_match_attendance

from .router import router

_OPERABLE_STATES = (
    MatchState.SCHEDULED,
    MatchState.LIVE,
    MatchState.HALF_TIME,
)


@router.get("/mine", response_model=MatchListResponse)
async def get_my_matches(
    currentUser=Depends(JwtRequired(roles=[PlatformRoles.OPERATOR])),
    db: Session = Depends(get_db),
):
    """The matches the signed-in account may score, soonest first.

    All staff accounts may score any open match. Assignments remain useful
    for coordination, but do not restrict access to the console.
    """
    query = db.query(MatchModel).options(
        joinedload(MatchModel.homeTeam),
        joinedload(MatchModel.awayTeam),
        joinedload(MatchModel.season),
        joinedload(MatchModel.field),
    )

    query = query.filter(MatchModel.state.in_(_OPERABLE_STATES))

    matches = query.order_by(MatchModel.timestamp.asc()).all()
    attach_match_attendance(db, matches)
    return MatchListResponse(data=matches)
