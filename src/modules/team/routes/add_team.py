from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.team.models import TeamAdd, TeamModel, TeamResponse

from .router import router


@router.post(
    "/",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def add_team(data: TeamAdd, db: Session = Depends(get_db)):
    existing = db.query(TeamModel).filter(TeamModel.name == data.name).first()
    if existing is not None:
        raise ErrorException(
            Error.CONFLICT,
            message="A team with this name already exists",
            status_code=status.HTTP_409_CONFLICT,
        )

    team = TeamModel(
        name=data.name,
        shortName=data.shortName,
        faculty=data.faculty,
        description=data.description,
        color=data.color,
        logo=data.logo,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team
