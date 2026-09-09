from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from modules.audit.models import AuditLogModel


def record(
    db: Session,
    user,
    action: str,
    entityType: str,
    entityId: Optional[int] = None,
    matchId: Optional[int] = None,
    summary: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AuditLogModel:
    """Append one audit row. Flushed, not committed - the caller owns the
    transaction, so the trail is written if and only if the change itself is.
    """
    entry = AuditLogModel(
        entityType=entityType,
        entityId=entityId,
        action=action,
        matchId=matchId,
        userId=getattr(user, "id", None),
        userNameSnapshot=getattr(user, "name", None),
        summary=summary,
        details=details,
    )
    db.add(entry)
    db.flush()
    return entry
