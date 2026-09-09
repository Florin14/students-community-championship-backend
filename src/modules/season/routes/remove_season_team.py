from fastapi import Depends, Path, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.match.models import MatchModel
from modules.season.models import SeasonModel, SeasonTeamModel
from modules.standings.models import StandingModel

from .router import router


@router.delete(
    "/{id}/teams/{teamId}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def remove_season_team(
    teamId: int = Path(...),
    season: SeasonModel = Depends(GetInstanceFromPath(SeasonModel)),
    db: Session = Depends(get_db),
):
    enrollment = (
        db.query(SeasonTeamModel)
        .filter(
            SeasonTeamModel.seasonId == season.id,
            SeasonTeamModel.teamId == teamId,
        )
        .first()
    )
    if enrollment is None:
        raise ErrorException(
            Error.NOT_FOUND,
            message="Team is not enrolled in this season",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    has_matches = (
        db.query(MatchModel.id)
        .filter(
            MatchModel.seasonId == season.id,
            or_(
                MatchModel.homeTeamId == teamId,
                MatchModel.awayTeamId == teamId,
            ),
        )
        .first()
        is not None
    )
    if has_matches:
        raise ErrorException(
            Error.CONFLICT,
            message="Team has matches in this season and cannot be removed",
            status_code=status.HTTP_409_CONFLICT,
        )

    db.query(StandingModel).filter(
        StandingModel.seasonId == season.id,
        StandingModel.teamId == teamId,
    ).delete()
    db.delete(enrollment)
    db.commit()
