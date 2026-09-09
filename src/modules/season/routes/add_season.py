from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.season.models import SeasonAdd, SeasonModel, SeasonResponse

from .router import router


@router.post(
    "/",
    response_model=SeasonResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def add_season(data: SeasonAdd, db: Session = Depends(get_db)):
    existing = db.query(SeasonModel).filter(SeasonModel.name == data.name).first()
    if existing is not None:
        raise ErrorException(
            Error.CONFLICT,
            message="A season with this name already exists",
            status_code=status.HTTP_409_CONFLICT,
        )

    season = SeasonModel(
        name=data.name,
        description=data.description,
        startDate=data.startDate,
        endDate=data.endDate,
        isActive=data.isActive,
    )
    db.add(season)
    db.flush()

    if season.isActive:
        db.query(SeasonModel).filter(SeasonModel.id != season.id).update(
            {SeasonModel.isActive: False}
        )

    db.commit()
    db.refresh(season)
    return season
