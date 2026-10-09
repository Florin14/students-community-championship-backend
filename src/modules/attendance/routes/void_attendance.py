from fastapi import Depends
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from modules.attendance.models import AttendanceItem, AttendanceModel, AttendanceVoid
from modules.attendance.services import void_attendance as void
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired

from .router import router


@router.post("/{id}/void", response_model=AttendanceItem)
async def void_attendance(data: AttendanceVoid, attendance: AttendanceModel = Depends(GetInstanceFromPath(AttendanceModel)), currentUser=Depends(JwtRequired(roles=[PlatformRoles.ADMIN])), db: Session = Depends(get_db)):
    result = void(db, attendance, currentUser, data.reason)
    db.commit()
    return result
