from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.season.models import SeasonModel, SeasonTeamModel, SeasonTeamsUpdate
from modules.team.models import TeamModel

from .router import router


@router.post(
    "/{id}/teams",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def set_season_teams(
    data: SeasonTeamsUpdate,
    season: SeasonModel = Depends(GetInstanceFromPath(SeasonModel)),
    db: Session = Depends(get_db),
):
    """Enroll the given teams in the season (already-enrolled teams are kept)."""
    team_ids = set(data.teamIds)
    if not team_ids:
        return

    found = (
        db.query(TeamModel.id).filter(TeamModel.id.in_(team_ids)).all()
    )
    found_ids = {row.id for row in found}
    missing = team_ids - found_ids
    if missing:
        raise ErrorException(
            Error.NOT_FOUND,
            message=f"Teams not found: {sorted(missing)}",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    enrolled_ids = {st.teamId for st in season.seasonTeams}
    for team_id in sorted(team_ids - enrolled_ids):
        db.add(SeasonTeamModel(seasonId=season.id, teamId=team_id))

    db.commit()
