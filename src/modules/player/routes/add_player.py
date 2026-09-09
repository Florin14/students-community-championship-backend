from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.player.models import PlayerAdd, PlayerModel, PlayerResponse
from modules.player.services import attach_player_stats
from modules.team.models import TeamModel

from .router import router


@router.post(
    "/",
    response_model=PlayerResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def add_player(data: PlayerAdd, db: Session = Depends(get_db)):
    if data.teamId is not None:
        team = db.query(TeamModel).filter(TeamModel.id == data.teamId).first()
        if team is None:
            raise ErrorException(
                Error.NOT_FOUND,
                message="Team not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    player = PlayerModel(
        name=data.name,
        position=data.position,
        shirtNumber=data.shirtNumber,
        avatar=data.avatar,
        teamId=data.teamId,
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    attach_player_stats(db, [player])
    return player
