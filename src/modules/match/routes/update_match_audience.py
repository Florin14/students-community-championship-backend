from fastapi import Depends, status
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from project_helpers.dependencies import MatchAccess, MatchContext
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.audit.services import record
from modules.match.models import MatchAudienceUpdate, MatchModel, MatchResponse
from modules.match.services import load_match_full

from .router import router


@router.put("/{id}/audience", response_model=MatchResponse)
async def update_match_audience(
    data: MatchAudienceUpdate,
    ctx: MatchContext = Depends(MatchAccess()),
    db: Session = Depends(get_db),
):
    match = (
        db.query(MatchModel)
        .filter(MatchModel.id == ctx.match.id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    if match.isLocked:
        raise ErrorException(Error.MATCH_LOCKED, status_code=status.HTTP_409_CONFLICT)
    previous = match.audience
    if previous != data.audience:
        match.audience = data.audience
        record(
            db, ctx.user, "MATCH_AUDIENCE_UPDATED", "MATCH",
            entityId=match.id, matchId=match.id,
            details={"previous": previous, "audience": match.audience},
        )
    db.commit()
    return load_match_full(db, match.id)
