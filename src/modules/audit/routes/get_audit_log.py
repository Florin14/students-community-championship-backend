from fastapi import Depends
from sqlalchemy.orm import Session, joinedload

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import JwtRequired
from modules.audit.models import (
    AuditLogListParams,
    AuditLogListResponse,
    AuditLogModel,
)

from .router import router


@router.get(
    "/",
    response_model=AuditLogListResponse,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def get_audit_log(
    params: AuditLogListParams = Depends(),
    db: Session = Depends(get_db),
):
    """The change history, newest first. Administrators only - it names the
    accounts behind every action.
    """
    query = db.query(AuditLogModel).options(joinedload(AuditLogModel.user))

    if params.matchId:
        query = query.filter(AuditLogModel.matchId == params.matchId)
    if params.entityType:
        query = query.filter(AuditLogModel.entityType == params.entityType)
    if params.userId:
        query = query.filter(AuditLogModel.userId == params.userId)

    query = query.order_by(
        AuditLogModel.createdAt.desc(), AuditLogModel.id.desc()
    )
    return AuditLogListResponse(data=params.apply(query).all())
