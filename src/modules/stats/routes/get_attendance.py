from fastapi import Depends
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from modules.attendance.models import AttendanceStatsParams, AttendanceStatsResponse
from modules.attendance.services import attendance_stats
from project_helpers.dependencies import JwtRequired

from .router import router


@router.get("/attendance", response_model=AttendanceStatsResponse, dependencies=[Depends(JwtRequired(roles=[PlatformRoles.OPERATOR]))])
async def get_attendance(params: AttendanceStatsParams = Depends(), db: Session = Depends(get_db)):
    return attendance_stats(db, params)
