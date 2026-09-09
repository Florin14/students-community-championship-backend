from fastapi import Depends

from project_helpers.dependencies import GetInstanceFromPath
from modules.team.models import TeamModel, TeamResponse

from .router import router


@router.get("/{id}", response_model=TeamResponse)
async def get_team(team: TeamModel = Depends(GetInstanceFromPath(TeamModel))):
    return team
