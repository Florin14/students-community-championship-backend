from fastapi import Depends
from sqlalchemy.orm import Session, joinedload

from constants import MatchState, PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import JwtRequired
from modules.match.models import (
    MatchListResponse,
    MatchModel,
    MatchOperatorModel,
)

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

    This is the operator's home screen. Admins and super-admins can score any
    match, so for them it lists every match still open for scoring rather than
    only their explicit assignments.
    """
    query = db.query(MatchModel).options(
        joinedload(MatchModel.homeTeam),
        joinedload(MatchModel.awayTeam),
        joinedload(MatchModel.season),
        joinedload(MatchModel.field),
    )

    if currentUser.covers(PlatformRoles.ADMIN):
        query = query.filter(MatchModel.state.in_(_OPERABLE_STATES))
    else:
        query = query.join(
            MatchOperatorModel,
            MatchOperatorModel.matchId == MatchModel.id,
        ).filter(MatchOperatorModel.userId == currentUser.id)

    matches = query.order_by(MatchModel.timestamp.asc()).all()
    return MatchListResponse(data=matches)
