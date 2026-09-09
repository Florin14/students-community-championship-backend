from fastapi import Depends
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from modules.match.models import MatchModel, MatchOperatorsSet, MatchResponse
from modules.match.services import load_match_full
from modules.match.services import set_match_operators as apply_operators

from .router import router


@router.put(
    "/{id}/operators",
    response_model=MatchResponse,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def set_match_operators(
    data: MatchOperatorsSet,
    match: MatchModel = Depends(GetInstanceFromPath(MatchModel)),
    db: Session = Depends(get_db),
):
    """Assign the operators who may score this match.

    Replaces the whole set, so sending an empty list clears the assignment and
    leaves the match to admins only.
    """
    apply_operators(db, match, data.operatorIds)
    db.commit()
    return load_match_full(db, match.id)
