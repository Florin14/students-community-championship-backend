from fastapi import Depends
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from modules.attendance.models import MatchAttendanceResponse
from modules.attendance.services import match_attendance
from modules.match.models import MatchModel
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired

from .router import router


@router.get("/matches/{id}", response_model=MatchAttendanceResponse, dependencies=[Depends(JwtRequired(roles=[PlatformRoles.OPERATOR]))])
async def get_match_attendance(match: MatchModel = Depends(GetInstanceFromPath(MatchModel)), db: Session = Depends(get_db)):
    return match_attendance(db, match)
