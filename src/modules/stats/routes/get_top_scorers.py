from typing import Optional

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from modules.stats.models import TopPlayersResponse

from .helpers import build_top_players
from .router import router


@router.get("/top-scorers", response_model=TopPlayersResponse)
async def get_top_scorers(
    seasonId: Optional[int] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    data = build_top_players(
        db,
        seasonId,
        sort_key=lambda s: (s["goals"], s["assists"]),
        limit=limit,
        keep=lambda s: s["goals"] > 0,
    )
    return TopPlayersResponse(data=data)
