from fastapi import Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from extensions.sqlalchemy import get_db
from modules.season.models import SeasonTeamModel
from modules.team.models import TeamListParams, TeamListResponse, TeamModel

from .router import router


@router.get("/", response_model=TeamListResponse)
async def get_teams(
    params: TeamListParams = Depends(),
    db: Session = Depends(get_db),
):
    query = db.query(TeamModel).options(joinedload(TeamModel.players))

    if params.seasonId:
        query = query.join(
            SeasonTeamModel, SeasonTeamModel.teamId == TeamModel.id
        ).filter(SeasonTeamModel.seasonId == params.seasonId)

    if params.search:
        pattern = f"%{params.search}%"
        query = query.filter(or_(
            TeamModel.name.ilike(pattern),
            TeamModel.faculty.ilike(pattern),
            TeamModel.university.ilike(pattern),
        ))

    query = query.order_by(TeamModel.name.asc())

    return TeamListResponse(data=params.apply(query).all())
