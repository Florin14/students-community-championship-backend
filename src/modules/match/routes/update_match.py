from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.match.models import MatchModel, MatchResponse, MatchUpdate
from modules.season.services import ensure_team_enrolled
from modules.standings.services import recalculate_standings_for_teams
from modules.team.models import TeamModel

from .router import router


@router.put(
    "/{id}",
    response_model=MatchResponse,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def update_match(
    data: MatchUpdate,
    match: MatchModel = Depends(GetInstanceFromPath(MatchModel)),
    db: Session = Depends(get_db),
):
    previous_team_ids = {match.homeTeamId, match.awayTeamId}

    home_team_id = (
        data.homeTeamId if data.homeTeamId is not None else match.homeTeamId
    )
    away_team_id = (
        data.awayTeamId if data.awayTeamId is not None else match.awayTeamId
    )
    if home_team_id == away_team_id:
        raise ErrorException(
            Error.BAD_REQUEST,
            message="A team cannot play against itself",
        )

    new_team_ids = {home_team_id, away_team_id} - previous_team_ids
    if new_team_ids:
        found = (
            db.query(TeamModel.id).filter(TeamModel.id.in_(new_team_ids)).all()
        )
        if len(found) != len(new_team_ids):
            raise ErrorException(
                Error.NOT_FOUND,
                message="One or both teams were not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    match.update(data)
    db.flush()

    for team_id in (match.homeTeamId, match.awayTeamId):
        ensure_team_enrolled(db, match.seasonId, team_id)

    recalculate_standings_for_teams(
        db,
        match.seasonId,
        previous_team_ids | {match.homeTeamId, match.awayTeamId},
    )

    db.commit()
    db.refresh(match)
    return match
