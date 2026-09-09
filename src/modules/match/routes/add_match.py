from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.match.models import MatchAdd, MatchModel, MatchResponse
from modules.season.models import SeasonModel
from modules.season.services import ensure_team_enrolled
from modules.team.models import TeamModel

from .router import router


@router.post(
    "/",
    response_model=MatchResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def add_match(data: MatchAdd, db: Session = Depends(get_db)):
    if data.homeTeamId == data.awayTeamId:
        raise ErrorException(
            Error.BAD_REQUEST,
            message="A team cannot play against itself",
        )

    season = (
        db.query(SeasonModel).filter(SeasonModel.id == data.seasonId).first()
    )
    if season is None:
        raise ErrorException(
            Error.NOT_FOUND,
            message="Season not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    teams = (
        db.query(TeamModel)
        .filter(TeamModel.id.in_([data.homeTeamId, data.awayTeamId]))
        .all()
    )
    if len(teams) != 2:
        raise ErrorException(
            Error.NOT_FOUND,
            message="One or both teams were not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    match = MatchModel(
        seasonId=data.seasonId,
        homeTeamId=data.homeTeamId,
        awayTeamId=data.awayTeamId,
        round=data.round,
        timestamp=data.timestamp,
        location=data.location,
    )
    db.add(match)
    db.flush()

    ensure_team_enrolled(db, data.seasonId, data.homeTeamId)
    ensure_team_enrolled(db, data.seasonId, data.awayTeamId)

    db.commit()
    db.refresh(match)
    return match
