from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from modules.season.models import SeasonModel

from .router import router


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def delete_season(
    season: SeasonModel = Depends(GetInstanceFromPath(SeasonModel)),
    db: Session = Depends(get_db),
):
    db.delete(season)
    db.commit()
