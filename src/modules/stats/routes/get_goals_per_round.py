from typing import Optional

from fastapi import Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from modules.match.models import MatchModel
from modules.match.services import completed_match_filter
from modules.stats.models import GoalsPerRoundItem, GoalsPerRoundResponse

from .router import router


@router.get("/goals-per-round", response_model=GoalsPerRoundResponse)
async def get_goals_per_round(
    seasonId: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(
        MatchModel.round,
        func.count(MatchModel.id),
        func.sum(MatchModel.scoreHome + MatchModel.scoreAway),
    ).filter(completed_match_filter())

    if seasonId:
        query = query.filter(MatchModel.seasonId == seasonId)

    rows = query.group_by(MatchModel.round).all()
    rows.sort(key=lambda row: (row[0] is None, row[0] or 0))

    data = [
        GoalsPerRoundItem(round=round_, matches=matches, goals=int(goals or 0))
        for round_, matches, goals in rows
    ]
    return GoalsPerRoundResponse(data=data)
