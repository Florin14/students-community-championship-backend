from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from modules.player.models import PlayerModel
from modules.player.models.player_qr_schemas import PlayerQrRevoke
from modules.player.services.qr_service import revoke_player_qr as revoke
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired

from .router import router


@router.post("/{id}/qr/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_player_qr(data: PlayerQrRevoke, player: PlayerModel = Depends(GetInstanceFromPath(PlayerModel)), currentUser=Depends(JwtRequired(roles=[PlatformRoles.ADMIN])), db: Session = Depends(get_db)):
    revoke(db, player, data.seasonId, currentUser)
    db.commit()
