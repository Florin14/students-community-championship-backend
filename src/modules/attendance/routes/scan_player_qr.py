from fastapi import Depends
from sqlalchemy.orm import Session

from constants import AttendanceStatus, PlatformRoles
from extensions.sqlalchemy import get_db
from modules.attendance.models import AttendanceScan, AttendanceScanResponse
from modules.attendance.services import can_confirm, find_attendance
from modules.match.models import MatchModel
from modules.player.services import attach_player_stats
from modules.player.services.qr_service import resolve_player_qr
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired

from .router import router


@router.post("/matches/{id}/scan", response_model=AttendanceScanResponse, dependencies=[Depends(JwtRequired(roles=[PlatformRoles.OPERATOR]))])
async def scan_player_qr(data: AttendanceScan, match: MatchModel = Depends(GetInstanceFromPath(MatchModel)), db: Session = Depends(get_db)):
    player = resolve_player_qr(db, data.token, match)
    attach_player_stats(db, [player], season_id=match.seasonId)
    attendance = find_attendance(db, match.id, player.id)
    return AttendanceScanResponse(matchId=match.id, player=player,
        alreadyPresent=bool(attendance and attendance.status == AttendanceStatus.PRESENT),
        canConfirm=can_confirm(match), attendance=attendance)
