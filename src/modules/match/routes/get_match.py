from fastapi import Depends, Path, status
from sqlalchemy.orm import Session, joinedload

from extensions.sqlalchemy import get_db
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.match.models import CardModel, GoalModel, MatchModel, MatchResponse

from .router import router


@router.get("/{id}", response_model=MatchResponse)
async def get_match(id: int = Path(...), db: Session = Depends(get_db)):
    match = (
        db.query(MatchModel)
        .options(
            joinedload(MatchModel.homeTeam),
            joinedload(MatchModel.awayTeam),
            joinedload(MatchModel.season),
            joinedload(MatchModel.goals).joinedload(GoalModel.scorer),
            joinedload(MatchModel.goals).joinedload(GoalModel.assistPlayer),
            joinedload(MatchModel.cards).joinedload(CardModel.player),
        )
        .filter(MatchModel.id == id)
        .first()
    )

    if match is None:
        raise ErrorException(
            Error.NOT_FOUND,
            message="Match not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    match.goals.sort(key=lambda g: (g.minute is None, g.minute or 0, g.id))
    match.cards.sort(key=lambda c: (c.minute is None, c.minute or 0, c.id))

    return match
