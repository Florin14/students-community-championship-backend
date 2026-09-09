from typing import Optional

from fastapi import Depends, Query
from sqlalchemy.orm import Session, joinedload

from extensions.sqlalchemy import get_db
from modules.player.models import (
    PlayerListParams,
    PlayerListResponse,
    PlayerModel,
)
from modules.player.services import attach_player_stats

from .router import router


@router.get("/", response_model=PlayerListResponse)
async def get_players(
    params: PlayerListParams = Depends(),
    seasonId: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(PlayerModel).options(joinedload(PlayerModel.team))

    if params.teamId:
        query = query.filter(PlayerModel.teamId == params.teamId)

    if params.position:
        query = query.filter(PlayerModel.position == params.position)

    if params.search:
        query = query.filter(PlayerModel.name.ilike(f"%{params.search}%"))

    query = query.order_by(PlayerModel.name.asc())
    players = params.apply(query).all()

    attach_player_stats(db, players, season_id=seasonId)

    return PlayerListResponse(data=players)
