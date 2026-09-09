from fastapi import Depends, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.match.models import MatchModel
from modules.team.models import TeamModel

from .router import router


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def delete_team(
    team: TeamModel = Depends(GetInstanceFromPath(TeamModel)),
    db: Session = Depends(get_db),
):
    has_matches = (
        db.query(MatchModel.id)
        .filter(
            or_(
                MatchModel.homeTeamId == team.id,
                MatchModel.awayTeamId == team.id,
            )
        )
        .first()
        is not None
    )
    if has_matches:
        raise ErrorException(
            Error.CONFLICT,
            message="Team has matches and cannot be deleted",
            status_code=status.HTTP_409_CONFLICT,
        )

    db.delete(team)
    db.commit()
