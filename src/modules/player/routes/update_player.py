from datetime import datetime

from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.player.models import PlayerModel, PlayerQrModel, PlayerResponse, PlayerUpdate
from modules.player.services import attach_player_stats
from modules.team.models import TeamModel

from .router import router


@router.put(
    "/{id}",
    response_model=PlayerResponse,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def update_player(
    data: PlayerUpdate,
    player: PlayerModel = Depends(GetInstanceFromPath(PlayerModel)),
    db: Session = Depends(get_db),
):
    player = (
        db.query(PlayerModel)
        .filter(PlayerModel.id == player.id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    if not (data.avatar if "avatar" in data.model_fields_set else player.avatar):
        raise ErrorException(Error.PLAYER_PHOTO_REQUIRED, status_code=400)
    if data.teamId is not None:
        team = db.query(TeamModel).filter(TeamModel.id == data.teamId).first()
        if team is None:
            raise ErrorException(
                Error.NOT_FOUND,
                message="Team not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    # Moving to another team invalidates every previously distributed QR.
    if "teamId" in data.model_fields_set and data.teamId != player.teamId:
        from constants import AttendanceStatus
        from modules.attendance.models import AttendanceModel
        from modules.match.models import MatchModel

        pending_presence = (
            db.query(AttendanceModel.id)
            .join(MatchModel, MatchModel.id == AttendanceModel.matchId)
            .filter(
                AttendanceModel.playerId == player.id,
                AttendanceModel.status == AttendanceStatus.PRESENT,
                MatchModel.startedAt.is_(None),
            )
            .first()
        )
        if pending_presence is not None:
            raise ErrorException(
                Error.CONFLICT,
                message="Correct pending match attendance before transferring this player",
                status_code=status.HTTP_409_CONFLICT,
            )
        db.query(PlayerQrModel).filter(
            PlayerQrModel.playerId == player.id,
            PlayerQrModel.revokedAt.is_(None),
        ).update(
            {PlayerQrModel.revokedAt: datetime.utcnow()},
            synchronize_session="fetch",
        )
    player.update(data)
    db.commit()
    db.refresh(player)

    attach_player_stats(db, [player])
    return player
