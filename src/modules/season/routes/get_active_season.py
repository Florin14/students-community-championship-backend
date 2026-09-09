from fastapi import Depends, status
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.season.models import SeasonModel, SeasonResponse

from .router import router


@router.get("/active", response_model=SeasonResponse)
async def get_active_season(db: Session = Depends(get_db)):
    season = (
        db.query(SeasonModel)
        .filter(SeasonModel.isActive.is_(True))
        .first()
    )

    if season is None:
        season = (
            db.query(SeasonModel)
            .order_by(SeasonModel.startDate.desc().nullslast(), SeasonModel.id.desc())
            .first()
        )

    if season is None:
        raise ErrorException(
            Error.NOT_FOUND,
            message="No season available yet",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return season
