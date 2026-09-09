from typing import Optional

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from modules.stats.models import TopPlayersResponse

from .helpers import build_top_players
from .router import router


@router.get("/top-assists", response_model=TopPlayersResponse)
async def get_top_assists(
    seasonId: Optional[int] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    data = build_top_players(
        db,
        seasonId,
        sort_key=lambda s: (s["assists"], s["goals"]),
        limit=limit,
        keep=lambda s: s["assists"] > 0,
    )
    return TopPlayersResponse(data=data)
