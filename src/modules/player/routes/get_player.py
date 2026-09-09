from typing import Optional

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath
from modules.player.models import PlayerModel, PlayerResponse
from modules.player.services import attach_player_stats

from .router import router


@router.get("/{id}", response_model=PlayerResponse)
async def get_player(
    seasonId: Optional[int] = Query(None),
    player: PlayerModel = Depends(GetInstanceFromPath(PlayerModel)),
    db: Session = Depends(get_db),
):
    attach_player_stats(db, [player], season_id=seasonId)
    return player
