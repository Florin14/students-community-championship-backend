from fastapi import Depends, Query
from sqlalchemy.orm import Session, joinedload

from extensions.sqlalchemy import get_db
from modules.standings.models import StandingListResponse, StandingModel
from modules.standings.services import build_form_map

from .router import router


@router.get("/", response_model=StandingListResponse)
async def get_standings(
    seasonId: int = Query(..., alias="seasonId"),
    db: Session = Depends(get_db),
):
    standings = (
        db.query(StandingModel)
        .options(joinedload(StandingModel.team))
        .filter(StandingModel.seasonId == seasonId)
        .all()
    )

    form_map = build_form_map(db, seasonId)
    for standing in standings:
        standing.form = form_map.get(standing.teamId, "")

    standings.sort(
        key=lambda s: (
            -s.points,
            -s.goalDiff,
            -s.goalsFor,
            (s.teamName or "").lower(),
        )
    )

    return StandingListResponse(data=standings)
