from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from modules.match.models import MatchModel
from modules.standings.services import recalculate_standings_for_teams

from .router import router


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def delete_match(
    match: MatchModel = Depends(GetInstanceFromPath(MatchModel)),
    db: Session = Depends(get_db),
):
    season_id = match.seasonId
    team_ids = [match.homeTeamId, match.awayTeamId]

    db.delete(match)
    db.flush()

    recalculate_standings_for_teams(db, season_id, team_ids)
    db.commit()
