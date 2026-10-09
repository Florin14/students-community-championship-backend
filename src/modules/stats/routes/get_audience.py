from fastapi import Depends
from sqlalchemy.orm import Session, joinedload

from extensions.sqlalchemy import get_db
from modules.match.models import MatchModel
from modules.stats.models import AudienceMatchItem, AudienceStatsParams, AudienceStatsResponse
from modules.stats.services import audience_query, audience_summary

from .router import router


@router.get("/audience", response_model=AudienceStatsResponse)
async def get_audience(
    params: AudienceStatsParams = Depends(),
    db: Session = Depends(get_db),
):
    query = audience_query(db, params.seasonId).options(
        joinedload(MatchModel.homeTeam), joinedload(MatchModel.awayTeam),
    ).order_by(MatchModel.audience.desc(), MatchModel.timestamp.asc(), MatchModel.id.asc())
    matches = params.apply(query).all()
    return AudienceStatsResponse(
        **audience_summary(db, params.seasonId),
        data=[AudienceMatchItem(
            matchId=match.id, timestamp=match.timestamp, round=match.round,
            homeTeamName=match.homeTeamName, awayTeamName=match.awayTeamName,
            audience=match.audience,
        ) for match in matches],
    )
