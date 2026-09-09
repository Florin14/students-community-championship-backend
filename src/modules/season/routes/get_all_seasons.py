from fastapi import Depends
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from modules.season.models import (
    SeasonListParams,
    SeasonListResponse,
    SeasonModel,
)

from .router import router


@router.get("/", response_model=SeasonListResponse)
async def get_seasons(
    params: SeasonListParams = Depends(),
    db: Session = Depends(get_db),
):
    query = db.query(SeasonModel).order_by(
        SeasonModel.isActive.desc(),
        SeasonModel.startDate.desc().nullslast(),
        SeasonModel.id.desc(),
    )
    return SeasonListResponse(data=params.apply(query).all())
