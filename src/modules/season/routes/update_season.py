from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.season.models import SeasonModel, SeasonResponse, SeasonUpdate

from .router import router


@router.put(
    "/{id}",
    response_model=SeasonResponse,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def update_season(
    data: SeasonUpdate,
    season: SeasonModel = Depends(GetInstanceFromPath(SeasonModel)),
    db: Session = Depends(get_db),
):
    if data.name is not None and data.name != season.name:
        existing = (
            db.query(SeasonModel).filter(SeasonModel.name == data.name).first()
        )
        if existing is not None:
            raise ErrorException(
                Error.CONFLICT,
                message="A season with this name already exists",
                status_code=status.HTTP_409_CONFLICT,
            )

    season.update(data)
    db.flush()

    if season.isActive:
        db.query(SeasonModel).filter(SeasonModel.id != season.id).update(
            {SeasonModel.isActive: False}
        )

    db.commit()
    db.refresh(season)
    return season
