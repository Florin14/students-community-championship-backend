from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.team.models import TeamModel, TeamResponse, TeamUpdate

from .router import router


@router.put(
    "/{id}",
    response_model=TeamResponse,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def update_team(
    data: TeamUpdate,
    team: TeamModel = Depends(GetInstanceFromPath(TeamModel)),
    db: Session = Depends(get_db),
):
    if data.name is not None and data.name != team.name:
        existing = db.query(TeamModel).filter(TeamModel.name == data.name).first()
        if existing is not None:
            raise ErrorException(
                Error.CONFLICT,
                message="A team with this name already exists",
                status_code=status.HTTP_409_CONFLICT,
            )

    team.update(data)
    db.commit()
    db.refresh(team)
    return team
