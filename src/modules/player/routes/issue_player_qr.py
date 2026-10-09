from fastapi import Depends
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from modules.player.models import PlayerModel
from modules.player.models.player_qr_schemas import PlayerQrRequest, PlayerQrResponse
from modules.player.services.qr_service import issue_player_qr as issue
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired

from .router import router


@router.post("/{id}/qr", response_model=PlayerQrResponse)
async def issue_player_qr(data: PlayerQrRequest, player: PlayerModel = Depends(GetInstanceFromPath(PlayerModel)), currentUser=Depends(JwtRequired(roles=[PlatformRoles.ADMIN])), db: Session = Depends(get_db)):
    response = issue(db, player, data.seasonId, currentUser, data.regenerate)
    db.commit()
    return response
