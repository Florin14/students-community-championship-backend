from fastapi import Depends
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from modules.attendance.models import AttendanceConfirm, AttendanceConfirmResponse
from modules.attendance.services import confirm_attendance as confirm
from modules.match.models import MatchModel
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired

from .router import router


@router.post("/matches/{id}/confirm", response_model=AttendanceConfirmResponse)
async def confirm_attendance(data: AttendanceConfirm, match: MatchModel = Depends(GetInstanceFromPath(MatchModel)), currentUser=Depends(JwtRequired(roles=[PlatformRoles.OPERATOR])), db: Session = Depends(get_db)):
    attendance, repeated = confirm(db, match, data.token, currentUser, data.identityConfirmed)
    db.commit()
    return AttendanceConfirmResponse(attendance=attendance, alreadyPresent=repeated)
