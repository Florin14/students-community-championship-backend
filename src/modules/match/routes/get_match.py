from fastapi import Depends, Path, status
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.match.models import MatchResponse
from modules.match.services import load_match_full

from .router import router


@router.get("/{id}", response_model=MatchResponse)
async def get_match(id: int = Path(...), db: Session = Depends(get_db)):
    match = load_match_full(db, id)

    if match is None:
        raise ErrorException(
            Error.NOT_FOUND,
            message="Match not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    match.goals.sort(key=lambda g: (g.minute is None, g.minute or 0, g.id))
    match.cards.sort(key=lambda c: (c.minute is None, c.minute or 0, c.id))

    return match
