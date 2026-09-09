from fastapi import Depends

from project_helpers.dependencies import GetInstanceFromPath
from modules.season.models import SeasonModel, SeasonResponse

from .router import router


@router.get("/{id}", response_model=SeasonResponse)
async def get_season(
    season: SeasonModel = Depends(GetInstanceFromPath(SeasonModel)),
):
    return season
