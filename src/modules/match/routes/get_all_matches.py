from fastapi import Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from extensions.sqlalchemy import get_db
from modules.match.models import MatchListParams, MatchListResponse, MatchModel

from .router import router


@router.get("/", response_model=MatchListResponse)
async def get_matches(
    params: MatchListParams = Depends(),
    db: Session = Depends(get_db),
):
    query = db.query(MatchModel).options(
        joinedload(MatchModel.homeTeam),
        joinedload(MatchModel.awayTeam),
        joinedload(MatchModel.season),
    )

    if params.seasonId:
        query = query.filter(MatchModel.seasonId == params.seasonId)

    if params.teamId:
        query = query.filter(
            or_(
                MatchModel.homeTeamId == params.teamId,
                MatchModel.awayTeamId == params.teamId,
            )
        )

    if params.round:
        query = query.filter(MatchModel.round == params.round)

    if params.state:
        query = query.filter(MatchModel.state == params.state)

    query = query.order_by(MatchModel.timestamp.asc(), MatchModel.id.asc())

    return MatchListResponse(data=params.apply(query).all())
